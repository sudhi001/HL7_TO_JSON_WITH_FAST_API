# HL7_TO_JSON_WITH_FAST_API

## Overview

The purpose of this application is to provide developers and beginners with a secure way to parse HL7 messages. Using other online tools for real data validation might lead to HIPAA violations and compromise data security. This open-source application aims to address these concerns by allowing users to host and run the application in their own environment.

## Features

- Parse HL7 messages securely.
- Open-source with no data logging on the server.
- Provides an opportunity to run the application locally for enhanced security.

## Prerequisites

- Python latest version (minimum Python 3.11)

## Installation

1. **Clone the Repository:**
   ```bash
   git clone https://github.com/sudhi001/HL7_TO_JSON_WITH_FAST_API.git
   ```

2. **Navigate to the Project Folder:**
   ```bash
   cd HL7_TO_JSON_WITH_FAST_API
   ```

3. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

## Usage

4. **Run Fast API:**
   ```bash
   uvicorn main:app --reload
   ```

5. **Open the Application:**
   Open your browser and go to [http://localhost:8000](http://localhost:8000)

6. **Enjoy!**
   You can now use the application to parse HL7 messages in a secure environment.

## Note

- Ensure that you have the latest version of Python installed (minimum Python 3.11).

- While the application is hosted on a server, it's open-source, and no information is saved or logged on the server. If you still have security concerns, you have the option to run the application in your environment.

## About the Author

Hi, I'm Sudhi S., the creator of this HL7 to JSON parser. If you have any questions, suggestions, or feedback, feel free to reach out to me:

- Email: devsudhi@icloud.com
- GitHub: [sudhi001](https://github.com/sudhi001)

Happy coding!

