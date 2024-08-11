# EZ_ffmpeg

## Overview
EZ_ffmpeg is a Python-based GUI application designed to simplify video and audio processing tasks. The application allows users to batch process video files by normalizing audio levels and converting the audio to stereo format. The UI is sleek and intuitive, featuring a dark theme with dark aqua accents.

## Features
- **Audio Normalization:** Automatically normalizes the audio of the primary track using ffmpeg's capabilities.
- **Stereo Conversion:** Converts the primary audio track to stereo format while preserving the original video and subtitle tracks.
- **Batch Processing:** Queue multiple video files and process them sequentially.
- **Customizable Settings:** Adjust the MB/min rate and choose whether to replace the original files.
- **User-Friendly Interface:** Monitor processing progress with a responsive, visually appealing interface.

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

3. **Adjust Settings**:
   - Use the MB/min slider and checkboxes to customize the processing settings according to your needs.

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
