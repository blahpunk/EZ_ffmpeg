# EZ_ffmpeg

## Overview
EZ_ffmpeg is a Python-based GUI application that provides an intuitive interface for adjusting video settings. The app allows users to configure various video and audio processing options, including converting the primary audio track to stereo, adjusting MB/min rate, and batch processing multiple video files. The user interface is designed with a sleek, futuristic dark theme featuring dark aqua accents.

## Features
- **Adjustable Video Settings:** Easily configure video processing options such as MB/min rate, audio track conversion, and more through the user interface.
- **Stereo Conversion:** Convert the primary audio track to stereo format while preserving the original video and subtitle tracks.
- **Batch Processing:** Queue multiple video files and process them sequentially.
- **File Replacement Option:** Choose whether to replace the original file with the processed one.
- **User-Friendly Interface:** Monitor processing progress with real-time updates in a visually appealing interface.

## Requirements
- Python 3.8+
- `ffmpeg` installed and accessible from the command line.
- Python packages:
  - PyQt5

## Installation

### Clone the Repository
```bash
git clone https://github.com/blahpunk/EZ_ffmpeg.git
cd EZ_ffmpeg
```

### Install Dependencies
Install the required Python packages:
```bash
pip install -r requirements.txt
```

### Setting Up `ffmpeg`
Ensure `ffmpeg` is installed and accessible via the command line:
- **Windows**: Add the `ffmpeg` binary to your PATH.
- **Linux**: Install `ffmpeg` via your package manager (e.g., `sudo apt-get install ffmpeg`).

## Usage

### Running the Application
1. **Start the Application**:
   ```bash
   python main.py
   ```

2. **Select a Folder**:
   - Use the "Browse" button to select the folder containing the video files you want to process.

3. **Adjust Video Settings**:
   - Utilize the user interface to adjust various video settings such as the MB/min rate and audio track conversion options.

4. **Start Processing**:
   - Click the "Start" button to begin processing. The application will display real-time progress and status updates.

## Contributing
Contributions are welcome! To contribute:
- Fork the repository.
- Create a new branch for your feature or bug fix.
- Commit your changes and push them to your branch.
- Submit a pull request.

## License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgements
Special thanks to the `ffmpeg` community for their powerful media processing tools.
