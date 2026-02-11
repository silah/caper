# Caper - Selenium Test Builder

A web-based application for creating, managing, and executing Selenium browser automation tests with team collaboration features.

## Features

- **User Authentication** - Secure login with Flask-Login
- **Team Collaboration** - Share tests with your team using registration codes
- **Multi-Browser Support** - Test on Firefox, Chrome, Edge, and mobile browsers
- **Mobile Emulation** - Test mobile experiences with Chrome Mobile and Firefox Mobile
- **Visual Test Builder** - No coding required, build tests with a UI
- **Execution History** - Track test runs with detailed step-by-step results
- **Screenshots** - Capture screenshots during test execution

## Supported Browsers

- **Firefox** (Desktop) - Default, headless mode
- **Chrome** (Desktop) - Headless mode
- **Edge** (Desktop) - Headless mode  
- **Chrome Mobile** - Android emulation (375x812 viewport)
- **Firefox Mobile** - Android emulation (375x812 viewport)

## Quick Start with Docker

1. **Clone the repository**
   ```bash
   git clone https://github.com/silah/caper.git
   cd caper
   ```

2. **Build and run with Docker Compose**
   ```bash
   docker-compose up -d
   ```

3. **Access the application**
   - Open your browser to `http://localhost:5000`
   - Register a new user and create a team
   - Start building tests!

## Local Development

### Prerequisites
- Python 3.12+
- Firefox, Chrome, or Edge installed locally

### Setup

1. **Create virtual environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the application**
   ```bash
   python app.py
   ```

4. **Access at** `http://localhost:5000`

## Test Step Actions

- **Navigate to URL** - Open a webpage
- **Click Element** - Click on buttons, links, etc.
- **Type Text** - Fill in form fields
- **Wait** - Pause execution for X seconds
- **Execute JavaScript** - Run custom JS code
- **Take Screenshot** - Capture current page state
- **Assert Title** - Verify page title contains text
- **Assert Element Text** - Verify element contains text
- **Scroll To Element** - Scroll element into view

## Selector Types

- **CSS Selector** - `.classname`, `#id`, `tag[attribute='value']`
- **ID** - Element ID attribute
- **XPath** - Full XPath expressions
- **Name** - Element name attribute
- **Class** - Element class name
- **Tag** - HTML tag name
- **Link Text** - Exact link text

## Team Collaboration

1. **Creating a Team**
   - Register and select "Create a new team"
   - Save your registration code securely
   - Share the code with team members

2. **Joining a Team**
   - Register and select "Join an existing team"
   - Enter the registration code from your team admin
   - You'll have access to all team tests



## Environment Variables

Set in `docker-compose.yml` or create a `.env` file:

```env
SECRET_KEY=your-random-secret-key-here
FLASK_ENV=production
```

## Project Structure

```
caper/
├── app.py                  # Flask application
├── database.py             # SQLite database operations
├── test_generator.py       # Selenium script generation
├── models.py               # User model for Flask-Login
├── requirements.txt        # Python dependencies
├── Dockerfile              # Docker container definition
├── docker-compose.yml      # Docker Compose configuration
├── templates/              # HTML templates
│   ├── login.html
│   ├── register.html
│   ├── index.html
│   ├── create_test.html
│   ├── edit_test.html
│   ├── view_tests.html
│   └── view_executions.html
├── static/
│   ├── css/
│   │   └── style.css
│   ├── js/
│   │   └── app.js
│   └── screenshots/        # Test execution screenshots
└── tests.db                # SQLite database (auto-created)
```

## License

MIT

## Contributing

Pull requests are welcome! For major changes, please open an issue first to discuss what you would like to change.
