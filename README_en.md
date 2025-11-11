<!-- markdownlint-disable MD033 MD041 -->
<div align="center">

<img alt="LOGO" src="https://github.com/quietlysnow/MBCCtools/blob/main/resource/base/image/logo.jpg" width="256" height="256" />

# MBCCtools

A Path to Nowhere assistant tool based on MaaFramework. Image Technology + Simulated Control, Free Your Hands!
Powered by [MaaFramework](https://github.com/MaaXYZ/MaaFramework)!
</div>

## 📖 Project Description

This project is developed based on the [MACC](https://github.com/mxia9416/MACC) project. As the original project has not been updated for a long time and the author cannot be contacted, this project has been rewritten, referencing the design ideas of MACC during development.

This project is primarily implemented using a Pipeline low-code approach. Guidance and communication from developers are welcome.

> ⏰ This project is developed in personal spare time and updated casually. Found bugs will be fixed when possible, it is recommended to update to the latest version promptly.

### Implemented Features
- **Game Launch**: Close ads, check Sinner mood.
- **Guild Donation**
- **Friend Points Collection**
- **Daily Rewards**: Supervisor rewards, free packs, stamina collection.
- **Daily Dispatch**: Optional areas.
- **Stamina Stages**: Dark Zone, Memory Storm, Gold Rush, Seeds of Bad Omen, Extreme Search, Forbidden Area Investigation, Palma Ruins.
- **Battlepass Rewards**

Other features like material farming will be added later.

## Usage Instructions

Download: <https://github.com/quietlysnow/MBCCtools/releases>

#### Windows Users
- **Most Users**: Download `MBCCtools-win-x86_64.zip`
- **ARM Architecture Users**: Download `MBCCtools-win-aarch64.zip`  
  ⚠️ Note: The vast majority of Windows devices use x86_64 architecture. Unless you explicitly know your device uses ARM architecture, please choose the x86_64 version.
- Unzip and run `MFAAvalonia.exe`.
- I haven't used macOS, so I cannot provide usage instructions.

## Important Notes

**Application Error**: Usually due to missing runtime libraries. Please install [VC++ Redistributable](https://aka.ms/vs/17/release/vc_redist.x64.exe).
- **Compatibility**: Developed based on MuMu Simulator 5, 2560×1440 (280 DPI), Tablet version.
- **Resolution Recommendations**:
  - 1280×720 (240 DPI): Natively supported by MAA, best compatibility.
  - If encountering issues, try switching to 720p resolution.

## 🔧 Build Instructions

> ⚠️ This section is only relevant if you need to develop this project. Regular users should directly [download the release version](https://github.com/quietlysnow/MBCCtools/releases).

0. Clone this project and its submodules completely.

    ```bash
    git clone --recursive https://github.com/quietlysnow/MBCCtools.git
    ```

1. Download the MaaFramework [Release package](https://github.com/MaaXYZ/MaaFramework/releases) and extract it into the `deps` folder.
2. Run the install script.

    ```python
    python ./install.py
    ```

The generated binaries and related resource files are in the `install` directory.

## Development

- [MaaFW Development Approach](https://github.com/MaaXYZ/MaaFramework/blob/main/docs/zh_cn/1.1-%E5%BF%AB%E9%80%9F%E5%BC%80%E5%A7%8B.md#%E5%BC%80%E5%8F%91%E6%80%9D%E8%B7%AF)
  MBCCtools currently uses the first method described (Pure Pipeline low-code).
- [Pipeline Protocol](https://github.com/MaaXYZ/MaaFramework/blob/main/docs/zh_cn/3.1-%E4%BB%BB%E5%8A%A1%E6%B5%81%E6%B0%B4%E7%BA%BF%E5%8D%8F%E8%AE%AE.md)

Please visit the [MaaFramework](https://github.com/MaaXYZ/MaaFramework) main repository for more documentation.

## 🙏 Acknowledgments

This project is powered by **[MaaFramework](https://github.com/MaaXYZ/MaaFramework)**!

Thanks to the following developers for their contributions to this project (Replace the links below with your own project address if forking):

[![Contributors](https://contrib.rocks/image?repo=MaaXYZ/MaaFramework&max=1000)](https://github.com/MaaXYZ/MaaFramework/graphs/contributors)