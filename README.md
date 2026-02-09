# Selenium Test Builder

A Flask-based web application for creating and executing Selenium synthetic headless browser tests.

## Features

- **Visual Test Builder**: Create browser tests through an intuitive web interface
- **Multiple Actions**: Support for common browser interactions:
  - Navigate to URLs
  - Click elements
  - Type text into inputs
  - Wait for specified durations
  - Execute custom JavaScript
  - Take screenshots
  - Assert page titles and element text
  - Scroll to elements
- **SQLite Storage**: Tests and execution history stored in SQLite database
- **Headless Execution**: Tests run in headless Chrome browser
- **Execution History**: Track test runs and view detailed results

## Installation

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

2. Install Chrome/Chromium browser (for Selenium)

## Usage

1. Start the Flask application:
```bash
python app.py
```

2. Open your browser and navigate to `http://localhost:5000`

3. Create a new test:
   - Click "Create Test"
   - Enter test name and description
   - Add steps using the visual builder
   - Save the test

4. Execute tests:
   - Go to "View Tests"
   - Click "Run Test" on any saved test
   - View execution results and history

## Project Structure

```
caper/
├── app.py                 # Main Flask application
├── database.py            # Database operations
├── test_generator.py      # Selenium script generator
├── requirements.txt       # Python dependencies
├── templates/             # HTML templates
│   ├── index.html
│   ├── create_test.html
│   ├── view_tests.html
│   └── test_detail.html
└── static/               # Static assets
    ├── css/
    │   └── style.css
    └── js/
        └── app.js
```

## Supported Selector Types

- CSS Selector
- ID
- XPath
- Name
- Class Name
- Tag Name
- Link Text
- Partial Link Text

## License

MIT
