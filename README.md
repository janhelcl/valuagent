# Valuagent

**AI-powered OCR and validation system for Czech financial statements**

Valuagent is a sophisticated FastAPI application that extracts, validates, and processes Czech financial statements (Rozvaha - Balance Sheet, Výkaz zisku a ztráty - Profit & Loss Statement) from PDF annual reports using Google's Gemini AI models. The system provides automated OCR with intelligent validation rules and exports clean, structured data to Excel format.

## 🚀 Key Features

### 📄 Intelligent PDF Processing
- **Multi-format OCR**: Extracts financial data from Czech annual report PDFs
- **Automatic Statement Detection**: Identifies whether PDFs contain Balance Sheet, P&L, or both
- **Retry Logic**: Configurable OCR retry attempts for improved accuracy
- **Multi-file Processing**: Handle multiple PDF files simultaneously

### 🔍 Advanced Validation System
- **Business Rule Validation**: Pre-configured validation rules for Czech accounting standards
- **Tolerance Settings**: Configurable tolerance for rounding differences (common in "tis. Kč" statements)
- **Hierarchical Validation**: Validates parent-child relationships between financial line items
- **Error Reporting**: Detailed validation reports with specific error descriptions

### 📊 Data Export & Analysis
- **Excel Export**: Structured Excel workbooks with validation reports
- **JSON Output**: Clean, validated JSON data following Czech accounting standards
- **Validation Reports**: Dedicated sheets showing validation results and potential issues
- **Data Mapping**: Intelligent mapping of Czech financial statement line items

### 🌐 Modern Web Interface
- **Drag & Drop Upload**: Intuitive file upload interface
- **Real-time Processing**: Async processing with progress feedback
- **Multi-language Support**: Czech language interface and error messages
- **Responsive Design**: Works on desktop and mobile devices

### 🛡️ Enterprise Features
- **Rate Limiting**: Built-in API rate limiting for production use
- **Authentication**: Optional authentication system
- **Logging**: Comprehensive logging with Google Cloud Logging support
- **Docker Support**: Production-ready Docker containerization

## 🏗️ Architecture Overview

Valuagent follows a clean, domain-driven architecture:

```
src/
├── app/                    # FastAPI application layer
│   ├── api/               # API routes and endpoints
│   └── main.py            # Application entry point
├── domain/                # Core business logic
│   ├── models/           # Pydantic models for financial statements
│   └── prompts/          # AI prompts for OCR processing
├── infrastructure/       # External services and utilities
│   ├── clients/         # AI client integrations (Google Gemini)
│   ├── exporters/       # Excel and data export functionality
│   └── resources/       # Static resources and mappings
├── services/            # Application services
└── shared/              # Shared utilities
```

### Core Components

- **Domain Models**: Pydantic-based models for Balance Sheet and P&L statements with built-in validation
- **Validation Rules**: Configurable business rules that validate financial statement consistency
- **OCR Engine**: Google Gemini-powered OCR with specialized prompts for Czech financial documents
- **Export System**: Excel generation with formatted output and validation reports

## 🛠️ Setup & Installation

### Prerequisites

- **Python 3.10+**
- **Poetry** (for dependency management)
- **Google AI API Key** (for Gemini models)

### Local Development

1. **Clone the repository**:
```bash
git clone <repository-url>
cd valuagent
```

2. **Install dependencies**:
```bash
poetry install
```

3. **Set environment variables**:
```bash
# Windows
set GOOGLE_API_KEY=your_gemini_api_key_here
set GENAI_MODEL=gemini-2.5-pro

# Linux/macOS
export GOOGLE_API_KEY=your_gemini_api_key_here
export GENAI_MODEL=gemini-2.5-pro
```

4. **Start the development server**:
```bash
poetry run uvicorn src.app.main:app --reload --host 0.0.0.0 --port 8000
```

5. **Access the application**:
   - Web interface: http://localhost:8000
   - API documentation: http://localhost:8000/docs

### Docker Deployment

1. **Build the Docker image**:
```bash
docker build -t valuagent .
```

2. **Run the container**:
```bash
docker run -p 8080:8080 \
  -e GOOGLE_API_KEY=your_api_key \
  -e GENAI_MODEL=gemini-2.5-pro \
  valuagent
```

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `GOOGLE_API_KEY` | Google AI API key for Gemini models | - | Yes |
| `GENAI_MODEL` | Gemini model to use | `gemini-2.5-pro` | No |
| `LOG_LEVEL` | Logging level | `INFO` | No |
| `SESSION_SECRET` | Secret key for sessions | `change-this-in-prod` | No |
| `PORT` | Server port | `8080` | No |

## 📖 API Documentation

### Endpoints

#### `GET /`
Returns the main web interface for file upload.

#### `POST /process`
Process uploaded PDF files and return Excel or JSON output.

**Parameters:**
- `pdfs` (file, multiple): PDF files to process
- `tolerance` (int, default=1): Tolerance for validation rules
- `return_json` (bool, default=false): Return JSON instead of Excel
- `ocr_retries` (int, optional): Max OCR retry attempts

**Response:**
- Success: Excel file download or JSON data
- Error: JSON error message with details

### Example Usage

#### Using the Web Interface
1. Navigate to http://localhost:8000
2. Drag and drop PDF files or click to select
3. Adjust tolerance settings if needed
4. Click "Zpracovat a stáhnout Excel" to process

#### Using the API with curl
```bash
curl -X POST "http://localhost:8000/process" \
  -F "pdfs=@annual_report.pdf" \
  -F "tolerance=1" \
  -F "return_json=false"
```

#### Using Python requests
```python
import requests

with open('annual_report.pdf', 'rb') as f:
    response = requests.post(
        'http://localhost:8000/process',
        files={'pdfs': f},
        data={'tolerance': 1, 'return_json': False}
    )

# Save Excel file
with open('output.xlsx', 'wb') as f:
    f.write(response.content)
```

## 🎯 Supported Financial Statements

### Balance Sheet (Rozvaha)
- **Assets**: Current and non-current assets
- **Liabilities**: Current and long-term liabilities  
- **Equity**: Share capital, retained earnings, reserves
- **Validation Rules**: Asset-liability balance, hierarchical summations

### Profit & Loss Statement (Výkaz zisku a ztráty)
- **Revenue**: Operating revenue, financial income
- **Expenses**: Operating expenses, financial costs, taxes
- **Results**: Operating profit, profit before/after tax
- **Validation Rules**: Revenue-expense calculations, profit derivations

## 🔧 Configuration

### Tolerance Settings
The tolerance parameter allows for small rounding differences common in Czech financial statements (typically reported in thousands of CZK):

- `0`: Exact validation (no tolerance)
- `1`: Allow ±1 unit difference (recommended)
- `2+`: Higher tolerance for less precise documents

### OCR Retry Configuration
Configure retry attempts for improved accuracy:
- Default: 3 retries
- Maximum: 5 retries
- Minimum: 1 attempt

## 🧪 Development

### Project Structure
The project follows clean architecture principles with clear separation of concerns:

- **Domain Layer**: Business logic and validation rules
- **Application Layer**: API endpoints and request handling  
- **Infrastructure Layer**: External services and data persistence
- **Shared Layer**: Common utilities and helpers

### Running Tests
```bash
poetry run pytest
```

### Code Quality
```bash
# Format code
poetry run black src/

# Type checking
poetry run mypy src/

# Linting
poetry run flake8 src/
```

### Jupyter Notebooks
Explore the OCR functionality using the included Jupyter notebook:
```bash
poetry run jupyter lab notebooks/ocr.ipynb
```