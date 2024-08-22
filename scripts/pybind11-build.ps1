
# one notable step for this to work is to install `pybind11` headers. On Windows, install manually as mentions in this part of the [official docs](https://pybind11.readthedocs.io/en/stable/compiling.html#find-package-vs-add-subdirectory

# Get the directory of the script
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition

# Set the path to the dominator directory
$dominatorDir = Join-Path $scriptDir "..\dominator"

# Change directory to dominator subdirectory
Set-Location $dominatorDir

# Create the "build-windows" directory if it doesn't exist
New-Item -Path "build-windows" -ItemType Directory -Force

# Run CMake to configure and build the project
cmake.exe -S . -B "build-windows"
cmake.exe --build "build-windows" --config Release

# Move the built .pyd files to the dominator directory
$releaseDir = Join-Path "build-windows" "release"
Move-Item "$releaseDir\*.pyd" -Destination $dominatorDir
