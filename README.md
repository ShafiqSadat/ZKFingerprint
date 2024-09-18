
# ZKTeco Fingerprint Scanner in Python

The **ZKTeco Fingerprint Scanner** is an application built to interface with ZKTeco fingerprint devices using Python. 
The system stores fingerprints in an SQLite database and syncs them with the device upon connection. The UI is developed using Flet, providing an interactive and user-friendly interface.

## Features

- **Real-Time Device Sync**: Automatically connects to the fingerprint device and syncs fingerprints from the database.
- **Register New Fingerprints**: Capture and store new fingerprints, both in the local database and the device memory.
- **Identify Fingerprints**: Identifies stored fingerprints using both the device memory and the local database.
- **SQLite Database Integration**: Fingerprints are stored in a local SQLite database, ensuring persistent storage.
- **Lottie Animations for UI Feedback**: Smooth animations while registering and identifying fingerprints.
- **Thread-Safe Database Operations**: Ensures thread-safety when reading/writing to the SQLite database.
- **Supports ZKTeco Devices**: Works with ZKTeco devices such as SLK20R, ZK9500, and more.

## Prerequisites

Before running the application, ensure you have the following:

- On Linux and macOS: A .NET (or Mono) runtime is required to support ZKTeco SDKs and the C# wrapper. Windows is pre-configured with .NET by default.
- The ZKFinger SDK and its C# wrapper installed on your machine. You can download it from the official website [here](https://www.zkteco.com/en/Biometrics_Module_SDK/).
  - **Note**: Ensure the SDK and .NET wrapper are correctly set up in your environment (e.g., with paths set correctly to access the `.dll` files).
- This Application supports ZKTeco devices like SLK20R, ZK9500, ZK6500, ZK8500R.
1. **Python 3.8+** installed on your machine.
2. **Flet** installed for the UI.
3. **SQLite** (pre-installed with Python) for database storage.

### Python Libraries

You can install the required libraries by running the following command:

```bash
pip install -r requirements.txt
```

## Getting Started

### Clone the Repository

```bash
git clone https://github.com/ShafiqSadat/ZKFingerPrint.git
cd ZKFingerPrint
```

### Initialize the Database

The application will automatically create the `fingerprints.db` SQLite database in the project directory if it doesn't already exist.

### Running the Application

Run the application using Python:

```bash
python main.py
```

This will launch the Flet UI for the fingerprint scanner, providing options to register and identify fingerprints.

## Application Structure

- `main.py`: The core application logic for handling fingerprint registration, identification, and device connection.
- `assets/`: Contains Lottie animations and other static assets.
- `fingerprints.db`: SQLite database file where fingerprints are stored.

## Usage

1. **Connect to the Fingerprint Device**: The application attempts to connect to the ZKTeco supported device. If successful, all stored fingerprints from the database will be added to the device.
2. **Register Fingerprints**: You can register new fingerprints. The app captures multiple fingerprint templates, merges them, and saves them in both the device and database.
3. **Identify Fingerprints**: Users can identify fingerprints using the ZKTeco supported device. If a fingerprint is not found in the device, it checks the local database.

## Screenshots

![Registration Process Animation](https://s5.ezgif.com/tmp/ezgif-5-7e79ece354.gif)

## License

This project is licensed under the [MIT License](LICENSE).

## Contributions

Feel free to contribute by submitting a pull request or opening an issue for any bug reports or feature requests.

## Support

For any questions or help, please contact us via Telegram [@Shafiq](https://t.me/Shafiq).
