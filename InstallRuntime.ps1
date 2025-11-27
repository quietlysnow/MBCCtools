#Requires -RunAsAdministrator
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = "Stop"
$errorOccurred = $false  # 初始化错误标记

# 颜色输出函数
function Write-Color {
    param(
        [string]$Text,
        [ConsoleColor]$Color = [ConsoleColor]::White,
        [switch]$Bold
    )
    $originalColor = $Host.UI.RawUI.ForegroundColor
    Write-Host $Text -ForegroundColor $Color
    $Host.UI.RawUI.ForegroundColor = $originalColor
}

# 配置PowerShell执行策略
Write-Color -Text "`n========== 配置PowerShell执行策略 ==========" -Color Cyan
try {
    Set-ExecutionPolicy RemoteSigned -Scope CurrentUser -Force
    Write-Color -Text "执行策略设置成功（CurrentUser：RemoteSigned）" -Color Green
}
catch {
    Write-Color -Text "执行策略设置失败：$($_.Exception.Message), 请先手动执行“Set-ExecutionPolicy RemoteSigned -Scope CurrentUser -Force”" -Color Red
    Write-Color -Text "提示：若系统禁止修改执行策略，可手动通过「组策略」调整或运行 Get-Help Set-ExecutionPolicy 查看解决方案" -Color Yellow
}

# 检测系统架构
Write-Color -Text "`n========== 检测系统架构 ==========" -Color Cyan
$osArch = (Get-CimInstance -ClassName Win32_OperatingSystem).OSArchitecture
$arch = if ($osArch -eq "ARM64") { "arm64" } else { "x64" }
Write-Color -Text "检测到系统架构：$arch" -Color Green

# 手动下载并安装Microsoft Visual C++ Redistributable
function Install-VCRedist {
    param(
        [string]$Arch
    )
    Write-Color -Text "`n========== 安装VC++ Redistributable ==========" -Color Cyan
    # 官方下载链接
    $vcUrl = if ($Arch -eq "arm64") { 
        "https://aka.ms/vs/18/release/vc_redist.arm64.exe" 
    } else { 
        "https://aka.ms/vs/18/release/vc_redist.x64.exe" 
    }
    # 临时文件路径
    $vcTemp = Join-Path -Path $env:TEMP -ChildPath "vc_redist_$Arch.exe"

    try {
        # 下载安装包
        Write-Color -Text "正在下载VC++ Redistributable ($Arch)..." -Color Yellow
        # 启用基础解析，避免SSL/代理问题
        Invoke-WebRequest -Uri $vcUrl -OutFile $vcTemp -UseBasicParsing -TimeoutSec 300
        Write-Color -Text "VC++安装包下载完成，保存路径：$vcTemp" -Color Green

        # 静默安装（/repair：修复模式 /passive：被动安装 /norestart：不重启）
        Write-Color -Text "开始静默安装VC++ Redistributable..." -Color Yellow
        $installProcess = Start-Process -FilePath $vcTemp -ArgumentList "/repair /passive /norestart" -Wait -NoNewWindow -PassThru
        if ($installProcess.ExitCode -eq 0 -or $installProcess.ExitCode -eq 3010) {
            Write-Color -Text "VC++ Redistributable安装完成（退出码：$($installProcess.ExitCode)，3010表示需重启）" -Color Green
        } else {
            throw "VC++安装失败，退出码：$($installProcess.ExitCode)"
        }

        # 清理临时文件
        Remove-Item -Path $vcTemp -Force -ErrorAction SilentlyContinue
    }
    catch {
        Write-Color -Text "VC++ Redistributable安装失败：$($_.Exception.Message)" -Color Red
        $global:errorOccurred = $true
    }
}

# 手动下载并安装.NET Desktop Runtime 10
function Install-DotNetRuntime {
    param(
        [string]$Arch
    )
    Write-Color -Text "`n========== 安装.NET Desktop Runtime 10 ==========" -Color Cyan
    # 官方下载链接
    $dotnetUrl = if ($Arch -eq "arm64") { 
        "https://aka.ms/dotnet/10.0/windowsdesktop-runtime-win-arm64.exe" 
    } else { 
        "https://aka.ms/dotnet/10.0/windowsdesktop-runtime-win-x64.exe" 
    }
    # 临时文件路径
    $dotnetTemp = Join-Path -Path $env:TEMP -ChildPath "dotnet_runtime_10_$Arch.exe"

    try {
        # 下载安装包
        Write-Color -Text "正在下载.NET Desktop Runtime 10 ($Arch)..." -Color Yellow
        Invoke-WebRequest -Uri $dotnetUrl -OutFile $dotnetTemp -UseBasicParsing -TimeoutSec 300
        Write-Color -Text ".NET安装包下载完成，保存路径：$dotnetTemp" -Color Green

        # 静默安装
        Write-Color -Text "开始静默安装.NET Desktop Runtime 10..." -Color Yellow
        $installProcess = Start-Process -FilePath $dotnetTemp -ArgumentList "/repair /passive /norestart" -Wait -NoNewWindow -PassThru
        if ($installProcess.ExitCode -eq 0 -or $installProcess.ExitCode -eq 3010) {
            Write-Color -Text ".NET Desktop Runtime 10安装完成（退出码：$($installProcess.ExitCode)，3010表示需重启）" -Color Green
        } else {
            throw ".NET安装失败，退出码：$($installProcess.ExitCode)"
        }

        # 清理临时文件
        Remove-Item -Path $dotnetTemp -Force -ErrorAction SilentlyContinue
    }
    catch {
        Write-Color -Text ".NET Desktop Runtime 10安装失败：$($_.Exception.Message)" -Color Red
        $global:errorOccurred = $true
    }
}

# 执行安装
Install-VCRedist -Arch $arch
Install-DotNetRuntime -Arch $arch

# 输出安装结果与手动下载链接
Write-Color -Text "`n========== 安装结果 ==========" -Color Cyan
if (-not $errorOccurred) {
    Write-Color -Text "运行库修复完成！请重启电脑后再次尝试运行MFA。" -Color Green
    Write-Color -Text "The runtime library repair is complete. Please restart your computer and try running MAA again." -Color Green
}
else {
    Write-Color -Text "安装过程中出现错误，请手动下载以下组件安装：" -Color Red
    # VC++ Redist手动下载链接
    $vcUrl = if ($arch -eq "arm64") { "https://aka.ms/vs/18/release/vc_redist.arm64.exe" } else { "https://aka.ms/vs/18/release/vc_redist.x64.exe" }
    Write-Color -Text "`nMicrosoft Visual C++ Redistributable ($arch)：" -Color White
    Write-Color -Text $vcUrl -Color Cyan
    # .NET 10运行库手动下载链接
    $dotnetUrl = if ($arch -eq "arm64") { "https://aka.ms/dotnet/10.0/windowsdesktop-runtime-win-arm64.exe" } else { "https://aka.ms/dotnet/10.0/windowsdesktop-runtime-win-x64.exe" }
    Write-Color -Text "`n.NET Desktop Runtime 10 ($arch)：" -Color White
    Write-Color -Text $dotnetUrl -Color Cyan
}

# 等待用户按键退出
Write-Color -Text "`n按任意键退出..." -Color Yellow
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")