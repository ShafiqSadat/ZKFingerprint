import base64
import datetime
import os
import sqlite3
import sys
from io import BytesIO
from threading import Lock
from time import sleep

import flet as ft
from PIL import Image
from loguru import logger
from pyzkfp import ZKFP2


class FingerprintScanner:
    def __init__(self):
        # Configure loguru logger
        self.zkfp2 = None
        self.page = None
        self.is_connected = False
        self.templates = []
        self.cupertino_alert_dialog = None
        self.theme_toggle_icon = None
        self.device_connection_icon = None
        self.capture = None
        self.register = False
        self.fid = 1
        self.keep_alive = True

        # Add a threading lock to make database operations thread-safe
        self.db_lock = Lock()

        # Database setup (make thread-safe)
        self.db_connection = sqlite3.connect('fingerprints.db', check_same_thread=False)
        self.db_cursor = self.db_connection.cursor()
        logger.remove()  # Remove any default logger
        logger.add(sys.stdout, format="<white>{time:YYYY-MM-DD HH:mm:ss}</white> | "
                                      "<level>{level: <8}</level> | "
                                      "<cyan><b>{line}</b></cyan> - "
                                      "<white><b>{message}</b></white>",
                   colorize=True)

        self.logger = logger  # Assign loguru logger to self.logger

    def connect_to_device(self):
        connected = self.initialize_zkfp2()
        if connected:
            self.device_connection_icon.icon_color = ft.colors.GREEN
            self.device_connection_icon.icon = ft.icons.WIFI
            self.show_dialog(self.page, "Connection Success", "Successfully Connected to the fingerprint device.",
                             'success.json', False)
            self.setup_database()
            # Load fingerprints from the database and add them to the device
            self.load_fingerprints_from_db()
        else:
            self.show_dialog(self.page, "Connection Error", "Failed to connect to the fingerprint device.")

    def load_fingerprints_from_db(self):
        """Load fingerprints from the database and add them to the ZKFP device."""
        self.logger.info("Loading fingerprints from the database and adding to the device.")

        with self.db_lock:
            self.db_cursor.execute('SELECT user_id, fingerprint_template FROM fingerprints')
            rows = self.db_cursor.fetchall()

        for row in rows:
            user_id = row[0]
            fingerprint_template_base64 = row[1]

            # Decode the base64 encoded fingerprint template
            fingerprint_template = base64.b64decode(fingerprint_template_base64)

            # Add the fingerprint to the ZKFP2 device's memory
            self.add_fingerprint_to_zkfp(user_id, fingerprint_template)

        self.logger.info("All fingerprints from the database have been added to the device.")

    def add_fingerprint_to_zkfp(self, user_id, fingerprint_template):
        """Add the fingerprint template to the ZKFP2 device."""
        self.zkfp2.DBAdd(user_id, fingerprint_template)
        self.logger.info(f"Fingerprint for user {user_id} added to ZKFP2 database.")

    def get_next_user_id(self):
        """Get the next available user_id by checking the maximum user_id in the database."""
        with self.db_lock:
            self.db_cursor.execute('SELECT MAX(user_id) FROM fingerprints')
            result = self.db_cursor.fetchone()[0]
            return result + 1 if result else 1  # Start with user_id 1 if no records are found

    def setup_database(self):
        """Create the fingerprints table."""
        with self.db_lock:  # Use the lock to ensure thread-safe access
            self.db_cursor.execute('''
                CREATE TABLE IF NOT EXISTS fingerprints (
                    user_id INTEGER PRIMARY KEY,
                    fingerprint_template TEXT,
                    last_updated TIMESTAMP
                )
            ''')
            self.db_connection.commit()

    def initialize_zkfp2(self) -> bool:
        try:
            self.zkfp2 = ZKFP2()
            self.zkfp2.Init()
            device_count = self.zkfp2.GetDeviceCount()
            self.logger.info(f"{device_count} Devices found. Connecting to the first device.")
            self.zkfp2.OpenDevice(0)
            self.zkfp2.Light("green")
            self.zkfp2.DBClear()
            self.is_connected = True
            return True
        except Exception as e:
            self.logger.error(f"Failed to initialize ZKFP2 device: {e}")
            return False

    def capture_fingerprints(self):
        """Capture three fingerprints and merge them."""
        self.logger.info("Starting fingerprint capture process...")

        templates = []
        for i in range(3):
            while True:
                capture = self.zkfp2.AcquireFingerprint()
                if capture:
                    self.logger.info(f"Fingerprint {i + 1} captured")
                    tmp, img = capture
                    self.zkfp2.show_image(img)  # requires Pillow lib
                    templates.append(tmp)
                    break

        # Merge the three templates into one
        regTemp, regTempLen = self.zkfp2.DBMerge(*templates)
        if regTemp:
            self.logger.info("Fingerprints successfully merged.")
            return regTemp
        else:
            self.logger.error("Failed to merge fingerprints.")
            return None

    def register_new_fingerprint(self):
        """Automatically assign a new user_id and register the fingerprint."""
        user_id = self.get_next_user_id()  # Automatically get the next user_id
        regTemp = self.capture_fingerprints()
        regTemp_bytes = bytes(regTemp)  # Convert to Python bytes

        base64_encoded_data = base64.b64encode(regTemp_bytes)

        if regTemp is None:
            self.logger.error(f"Failed to register fingerprint for user {user_id}")
            return

        # Add the merged fingerprint template to the ZKFP2 device's database
        self.zkfp2.DBAdd(user_id, regTemp)
        self.save_fingerprint_to_db(user_id, base64_encoded_data)
        self.logger.info(f"Fingerprint for user {user_id} added to ZKFP2 database.")

    def save_fingerprint_to_db(self, user_id, fingerprint_template):
        """Save the fingerprint template to the SQLite database."""
        try:
            with self.db_lock:  # Ensure thread-safety
                self.db_cursor.execute(
                    'INSERT INTO fingerprints (user_id, fingerprint_template, last_updated) VALUES (?, ?, ?)',
                    (user_id, fingerprint_template,
                     datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                )
                self.db_connection.commit()
            self.logger.info(f"Fingerprint for user {user_id} saved to the local database.")
        except sqlite3.DatabaseError as e:
            self.logger.error(f"Failed to save fingerprint for user {user_id}: {e}")

    def add_fingerprint_to_zkfp(self, user_id, fingerprint_template):
        self.zkfp2.DBAdd(user_id, fingerprint_template)
        self.logger.info(f"Fingerprint for user {user_id} added to ZKFP2 database")

    def show_dialog(self, page, title, message, json_file='failed.json', repeat=True):
        def dismiss_dialog(e):
            self.cupertino_alert_dialog.open = False
            e.control.page.update()

        self.cupertino_alert_dialog = ft.CupertinoAlertDialog(
            title=ft.Text(title, text_align=ft.TextAlign.CENTER),
            actions=[
                ft.Lottie(src_base64=self.get_base64_src(json_file), repeat=repeat),
                ft.Container(
                    content=ft.Text(message, text_align=ft.TextAlign.CENTER, size=18),
                    margin=ft.margin.only(top=10, bottom=10)
                ),
                ft.CupertinoDialogAction(text="Close", is_destructive_action=True, on_click=dismiss_dialog),
            ],
        )
        page.overlay.append(self.cupertino_alert_dialog)
        self.cupertino_alert_dialog.open = True
        page.update()

    def create_app_bar_pages(self, page: ft.Page):
        return ft.AppBar(
            leading=ft.IconButton(ft.icons.ARROW_BACK, on_click=lambda e: page.go("/")),
            title=ft.Text("Madina Scanner"),
            center_title=False,
            bgcolor=ft.colors.SURFACE_VARIANT,
            actions=[
                self.theme_toggle_icon,
            ],
        )

    def create_app_bar(self, page: ft.Page):
        return ft.AppBar(
            leading=ft.Icon(ft.icons.FINGERPRINT),
            leading_width=40,
            title=ft.Text("Madina Scanner"),
            center_title=False,
            bgcolor=ft.colors.SURFACE_VARIANT,
            actions=[
                self.device_connection_icon,
                self.theme_toggle_icon,
            ],
        )

    def get_base64_src(self, json_file):
        # Check if running in a PyInstaller bundle
        try:
            base_path = sys._MEIPASS  # The temp folder where PyInstaller bundles files
        except AttributeError:
            base_path = os.path.abspath(".")

        # Build the full path to the asset
        json_file_path = os.path.join(base_path, f"assets/json/{json_file}")

        # Check if the file exists
        if not os.path.exists(json_file_path):
            self.logger.error(f"File not found: {json_file_path}")
            return None

        with open(json_file_path, "r", encoding="utf-8") as json_file:
            json_data = json_file.read()

        return base64.b64encode(json_data.encode('utf-8')).decode('utf-8')

    def change_theme_mode(self):
        if self.page.theme_mode == ft.ThemeMode.DARK:
            self.page.theme_mode = ft.ThemeMode.LIGHT
            self.theme_toggle_icon.icon = ft.icons.DARK_MODE
            self.page.update()
        else:
            self.page.theme_mode = ft.ThemeMode.DARK
            self.theme_toggle_icon.icon = ft.icons.LIGHT_MODE
            self.page.update()

    def register_page(self, page: ft.Page):
        text_display = ft.Text("Press Register button to get started!", size=30, text_align=ft.TextAlign.CENTER)

        # Lottie animation container
        lottie_container = ft.Container(
            content=ft.Lottie(src_base64=self.get_base64_src('finger.json')),  # Load Lottie animation
            width=500,
            height=500
        )

        # Directory where fingerprint images will be saved
        image_save_folder = "fingerprint_images"
        if not os.path.exists(image_save_folder):
            os.makedirs(image_save_folder)  # Create the folder if it doesn't exist

        def start_register(e):
            self.logger.info("Starting fingerprint registration process...")
            text_display.value = "Place your finger on the scanner for the first capture..."
            text_display.update()

            templates = []
            finger_image = None  # To store the image of the last finger capture

            # Capture fingerprints three times
            for i in range(3):
                text_display.value = f"Capturing fingerprint {i + 1} of 3..."
                text_display.update()
                while True:
                    capture = self.zkfp2.AcquireFingerprint()
                    if capture:
                        tmp, img = capture  # img is the raw byte data of the fingerprint image
                        finger_image = img  # Save the last captured image
                        # Check if the fingerprint already exists in the database
                        fid, score = self.zkfp2.DBIdentify(tmp)
                        if fid != 0:
                            # Fingerprint exists, show message and stop registration
                            self.show_dialog(page, "Fingerprint Exists",
                                             f"Fingerprint already registered with User ID: {fid}.",
                                             json_file='fingernok.json', repeat=False)
                            self.logger.info(f"Fingerprint already exists for User ID: {fid}")
                            text_display.value = f"Fingerprint already exists for User ID: {fid}. Registration canceled."
                            text_display.update()
                            return  # Stop the registration process

                        # If fingerprint does not exist, proceed with registration
                        templates.append(tmp)

                        # Display the captured fingerprint image in the UI
                        buffered = BytesIO()
                        image = Image.frombytes("L", (288, 375), img)  # Adjust the size according to your device
                        image.save(buffered, format="PNG")
                        img_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")

                        # Update Lottie container to show the captured fingerprint image
                        lottie_container.content = ft.Image(
                            src_base64=img_base64,  # Display the captured image
                        )
                        lottie_container.update()

                        self.logger.info(f"Fingerprint {i + 1} captured")
                        text_display.value = f"Fingerprint {i + 1} captured. Remove your finger."
                        text_display.update()
                        sleep(1)  # Short pause between captures
                        break
                    sleep(0.5)

            # Merge the three templates into one
            regTemp, regTempLen = self.zkfp2.DBMerge(*templates)
            if regTemp:
                user_id = self.get_next_user_id()  # Automatically assign a new user_id
                regTemp_bytes = bytes(regTemp)

                # Base64 encode the merged fingerprint template
                base64_encoded_data = base64.b64encode(regTemp_bytes).decode('utf-8')

                # Save the final fingerprint image as a PNG file (only one image)
                image = Image.frombytes("L", (288, 375), finger_image)
                image_filename = f"{image_save_folder}/user_{user_id}_fingerprint.png"
                image.save(image_filename)
                self.logger.info(f"Final fingerprint image saved as {image_filename}")

                # Add the fingerprint to the ZKFP device and save it to the database
                self.zkfp2.DBAdd(user_id, regTemp)
                self.save_fingerprint_to_db(user_id, base64_encoded_data)
                self.show_dialog(page, "Registration Success", f"User {user_id} successfully registered.", json_file='fingerok.json', repeat=False)
                self.logger.info(f"User {user_id} successfully registered.")
                text_display.value = f"User {user_id} successfully registered!"
            else:
                self.show_dialog(page, "Error", "Failed to merge fingerprints.")
                self.logger.error("Failed to merge fingerprints.")
                text_display.value = "Failed to merge fingerprints. Try again."

            text_display.update()

        page.views.append(
            ft.View(
                "/register",
                [
                    ft.Container(margin=ft.margin.only(bottom=40)),
                    ft.Column(
                        [
                            ft.Container(margin=ft.margin.only(bottom=40)),
                            text_display,
                            ft.Container(margin=ft.margin.only(bottom=40)),
                            lottie_container,  # Lottie animation container, updated during scanning
                            ft.ElevatedButton("Start Registration", on_click=start_register,
                                              icon=ft.icons.FINGERPRINT),
                        ],
                        expand=True,
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER
                    )
                ],
                appbar=self.create_app_bar_pages(page),
            )
        )
        page.update()

    def identify_page(self, page: ft.Page):
        text_display = ft.Text("Place your finger on the device!", size=30)

        # Initial Lottie animation for fingerprint
        lottie_container = ft.Container(
            content=ft.Lottie(src_base64=self.get_base64_src('finger.json')),
            width=500,
            height=500
        )

        def start_identification(e):
            self.logger.info("Starting identification process...")
            text_display.value = "Waiting for fingerprint..."
            text_display.update()
            page.update()

            # Wait for the fingerprint to be captured
            while True:
                capture = self.zkfp2.AcquireFingerprint()
                if capture:
                    # Break the loop once a fingerprint is captured
                    tmp, img = capture

                    # Display the fingerprint capture in the UI
                    buffered = BytesIO()
                    image = Image.frombytes("L", (288, 375), img)
                    image.save(buffered, format="PNG")
                    img_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")

                    lottie_container.content = ft.Image(
                        src_base64=img_base64,  # Display the captured image
                    )
                    lottie_container.update()

                    break
                self.logger.info("Waiting for fingerprint...")  # Optional logging for debugging
                sleep(0.5)  # Add a short delay to avoid excessive CPU usage

            # Identify fingerprint by matching with stored templates
            fid, score = self.zkfp2.DBIdentify(tmp)
            if fid != 0:
                self.logger.info(f"User identified: {fid}, Score: {score}")
                self.show_dialog(page, "User Identified", f"User ID: {fid}, Score: {score}.", json_file='fingerok.json',
                                 repeat=False)
                text_display.value = "Place your finger on the device!"
                text_display.update()
            else:
                # If fingerprint is not found in the device, check if it's in the database
                user_id = self.get_next_user_id()  # Get the next user_id to verify against the DB
                with self.db_lock:
                    self.db_cursor.execute("SELECT * FROM fingerprints WHERE user_id = ?", (user_id,))
                    row = self.db_cursor.fetchone()

                if row:
                    # If found in the DB but not in the device, add it to the device
                    fingerprint_template = row[1]
                    decoded_template = base64.b64decode(fingerprint_template)
                    self.zkfp2.DBAdd(user_id, decoded_template)
                    self.logger.info(f"User {user_id}'s fingerprint added from the database to the device.")
                    self.show_dialog(page, "User Found in Database",
                                     f"User ID: {user_id} fingerprint was added to the device.",
                                     json_file='fingerok.json', repeat=False)
                else:
                    # Fingerprint is not registered
                    self.show_dialog(page, "Identification Failed", "Fingerprint not recognized.",
                                     json_file='fingernok.json', repeat=False)
                    self.logger.info("Identification failed. Fingerprint not recognized.")

            text_display.update()

        page.views.append(
            ft.View(
                "/identify",
                [
                    ft.Container(margin=ft.margin.only(bottom=40)),
                    ft.Column(
                        [
                            ft.Container(margin=ft.margin.only(bottom=40)),
                            text_display,
                            ft.Container(margin=ft.margin.only(bottom=40)),
                            lottie_container,  # The container that will hold either Lottie or the captured image
                            ft.ElevatedButton("Start Identify", on_click=start_identification,
                                              icon=ft.icons.FINGERPRINT),
                        ],
                        expand=True,
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER
                    )
                ],
                appbar=self.create_app_bar_pages(page),
            )
        )
        page.update()

    def main_page(self, page: ft.Page):
        page.views.append(
            ft.View(
                "/",
                [
                    ft.Container(margin=ft.margin.only(bottom=40)),
                    ft.Column(
                        [
                            ft.Container(
                                content=ft.Lottie(src_base64=self.get_base64_src('biometric1.json'), ),
                            ),
                            ft.Container(margin=ft.margin.only(bottom=40)),
                            ft.Text("Select Biometric operation to continue!", size=30),
                            ft.Container(margin=ft.margin.only(bottom=40)),
                            ft.Row(
                                [
                                    ft.Container(
                                        content=ft.ResponsiveRow(
                                            [
                                                ft.Container(
                                                    content=ft.Lottie(
                                                        src_base64=self.get_base64_src('biometric3.json')),
                                                    width=200,
                                                    height=100
                                                ),
                                                ft.Text("Identify", text_align=ft.TextAlign.CENTER, size=18,
                                                        weight=ft.FontWeight.W_600)
                                            ]
                                        ),
                                        margin=10,
                                        padding=10,
                                        alignment=ft.alignment.center,
                                        bgcolor=ft.colors.BLUE_700,
                                        width=150,
                                        height=150,
                                        border_radius=10,
                                        ink=True,
                                        on_click=lambda e: page.go("/identify") if self.is_connected else self.show_dialog(page, "Connection Error", "Please connect to the fingerprint device."),
                                    ),
                                    ft.Container(
                                        content=ft.ResponsiveRow(
                                            [
                                                ft.Container(
                                                    content=ft.Lottie(
                                                        src_base64=self.get_base64_src('biometric2.json')),
                                                    width=200,
                                                    height=100
                                                ),
                                                ft.Text("Register", text_align=ft.TextAlign.CENTER, size=18,
                                                        weight=ft.FontWeight.W_600)
                                            ]
                                        ),
                                        margin=10,
                                        padding=10,
                                        alignment=ft.alignment.center,
                                        bgcolor=ft.colors.BLUE_700,
                                        width=150,
                                        height=150,
                                        border_radius=10,
                                        ink=True,
                                        on_click=lambda e: page.go("/register") if self.is_connected else self.show_dialog(page, "Connection Error", "Please connect to the fingerprint device.")
                                    ),
                                ],
                                alignment=ft.MainAxisAlignment.CENTER,
                            )
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER
                    )
                ],
                appbar=self.create_app_bar(page),
            )
        )
        page.update()

    def route_change(self, page: ft.Page):
        if page.route == "/":
            self.main_page(page)
        elif page.route == "/register":
            self.register_page(page)
        elif page.route == "/identify":
            self.identify_page(page)

    def app(self, page: ft.Page):
        self.page = page
        page.title = "Madina Finger Scanner"
        page.theme_mode = ft.ThemeMode.DARK
        page.window.icon = ft.icons.APPS
        page.window.width = 700
        page.window.height = 900
        page.window.resizable = False
        page.window.maximized = False
        self.theme_toggle_icon = ft.IconButton(ft.icons.LIGHT_MODE, on_click=lambda e: self.change_theme_mode(page))
        self.device_connection_icon = ft.IconButton(ft.icons.WIFI_OFF, on_click=lambda e: self.connect_to_device(),
                                                    icon_color=ft.colors.RED)
        page.appbar = ft.AppBar(
            leading=ft.Icon(ft.icons.FINGERPRINT),
            leading_width=40,
            title=ft.Text("MF Scanner"),
            center_title=False,
            bgcolor=ft.colors.SURFACE_VARIANT,
            actions=[
                self.device_connection_icon,
                self.theme_toggle_icon,
            ],
        )
        page.on_route_change = lambda e: self.route_change(page)
        page.go("/")


if __name__ == "__main__":
    fingerprint_scanner = FingerprintScanner()
    ft.app(
        fingerprint_scanner.app,
        assets_dir="assets",
    )
