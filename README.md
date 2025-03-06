# Screenshot OCR Web App

This is a web version of the original PyQt6 desktop screenshot application. It allows users to capture screenshots (full screen or by region), upload images, and extract text using Google's Gemini Vision API.

## Features

- Capture full screen screenshots
- Capture region-specific screenshots
- Upload images from your device
- Extract text from images using Gemini Vision
- Copy images to clipboard
- Copy extracted text to clipboard

## Project Structure

```
screenshot-ocr-web/
├── app.py                 # Main Flask application
├── requirements.txt       # Dependencies
├── templates/
│   └── index.html         # Main web interface
└── README.md              # Project documentation
```

## Deployment Instructions for Render.com

1. Push your code to a GitHub repository.

2. Sign up or log in to [Render.com](https://render.com/).

3. Click "New" and select "Web Service".

4. Connect your GitHub repository.

5. Configure the following settings:
   - **Name**: Your app name (e.g., screenshot-ocr-app)
   - **Environment**: Python
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app`

6. Add the following environment variables:
   - `GEMINI_API_KEY`: Your Google Gemini API key
   - `SECRET_KEY`: A random string for Flask session security
   - `FLASK_APP`: app.py

7. Click "Create Web Service".

## Local Development

1. Install the dependencies:
   ```
   pip install -r requirements.txt
   ```

2. Set environment variables:
   ```
   export GEMINI_API_KEY=your_gemini_api_key_here
   export SECRET_KEY=your_secret_key_here
   ```

3. Run the Flask application:
   ```
   flask run
   ```

4. Open your browser and navigate to `http://127.0.0.1:5000`

## Note on Screen Capture

Browser-based screen capture requires user permission and may have limitations compared to desktop applications. It works best in modern browsers with the Screen Capture API supported (Chrome, Edge, Firefox).

## Required Directory Structure

Create a templates folder to store the index.html file:

```
mkdir templates
mv index.html templates/
```
