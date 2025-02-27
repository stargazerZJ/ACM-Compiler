# Use the official Python image from the Alpine variant
FROM python:3.12-alpine

# Install the necessary packages
RUN apk add --no-cache clang18 make py3-pybind11-dev openjdk11 cmake

# Set the working directory in the container
WORKDIR /app

# Copy the requirements.txt file into the container
COPY requirements.txt ./

# Install the dependencies from the requirements.txt file
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container
COPY . .

# Execute the make build command
RUN make build

# Uninstall the build dependencies
RUN apk del clang18 openjdk11 cmake

# Execute the make run command
CMD ["make", "run"]
