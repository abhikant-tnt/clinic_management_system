# 🏥 Patient API Backend

This is a **FastAPI** backend for managing patient records, using a **dual PostgreSQL architecture**:
- **Local PostgreSQL**: Each clinic has its own local database instance
- **Main Server PostgreSQL**: Centralized server that aggregates data from all clinics
- **Tenant ID**: Each clinic is identified by a unique `tenant_id` to keep data separate

---

## 🚀 Getting Started

Follow these steps to set up and run the Patient API on your local machine.

### 📋 Prerequisites

You need the following installed **manually** (one-time setup):

1.  **Python 3.x** - Download from https://www.python.org/downloads/
2.  **PostgreSQL** - Download from https://www.postgresql.org/download/

**Everything else installs automatically!** (Prisma, GraphQL, FastAPI, etc. - see installation steps below)

### 📦 Installation on Doctor's Computer

**What needs manual installation:**
- ✅ Python 3.x (one-time)
- ✅ PostgreSQL (one-time)

**What installs automatically:**
- ✅ All Python packages (Prisma, GraphQL, FastAPI, etc.) - via `pip install -r requirements.txt`
- ✅ Prisma binaries (downloaded automatically when you run `generate_prisma.py`)
- ✅ Database tables (created automatically on first run)

**No need to manually install Prisma or GraphQL separately!** They're included in `requirements.txt`.

### 🛠️ Installation

1.  **Clone or download** this project folder.
2.  **Navigate** to the project directory in your terminal.
3.  **Install all Python packages** (this installs Prisma, GraphQL, FastAPI, etc. automatically):

    ```bash
    pip install -r requirements.txt
    ```
    
    **✅ This automatically installs:**
    - Prisma (database ORM)
    - Strawberry GraphQL (GraphQL support)
    - FastAPI (web framework)
    - All other dependencies
    
    **No manual installation needed for these!**

4.  **Generate Prisma Client** (optional, but recommended):

    You can use the provided script:
    ```bash
    python generate_prisma.py
    ```

    Or manually:
    ```bash
    python -m prisma py fetch    # Downloads Prisma binaries (one-time)
    python -m prisma py generate # Generates the Prisma Client
    ```

    **Note:** 
    - The Python `prisma` package automatically downloads Prisma binaries from the internet (no Node.js required)
    - Binaries are cached locally after first download
    - If Prisma generation fails, the application will automatically fall back to raw SQL queries
    - The app works fine without Prisma - it's optional but recommended for better type safety

### 💡 Installation Summary for Doctor's Computer

| Component | Installation Type | Notes |
|-----------|------------------|-------|
| **Python** | ⚠️ Manual | One-time, required - download from python.org |
| **PostgreSQL** | ⚠️ Manual | One-time, required - download from postgresql.org |
| **Python Packages** | ✅ Automatic | Via `pip install -r requirements.txt` |
| **Prisma** | ✅ Automatic | Included in Python packages - no separate install needed |
| **Prisma Binaries** | ✅ Automatic | Downloaded when running `generate_prisma.py` |
| **GraphQL (Strawberry)** | ✅ Automatic | Included in Python packages - no separate install needed |
| **Database Tables** | ✅ Automatic | Created on first run |
| **Database Schema** | ✅ Automatic | Created on first run |
| **.env File** | ✅ Automatic | Created on first run (needs configuration) |

**Answer:** When installing on a doctor's computer, only **Python** and **PostgreSQL** need to be installed manually. Everything else (Prisma, GraphQL, FastAPI, etc.) installs automatically when running `pip install -r requirements.txt`. No separate installation needed for Prisma or GraphQL!

### ▶️ Running the Server

1.  **Start the PostgreSQL server** (if it's not already running).
2.  **Configure PostgreSQL** (Optional - for password-free connection):
    - Run the setup script to enable password-free local connections:
      ```bash
      python app/core/setup_postgres_trust.py
      ```
    - Or manually configure `pg_hba.conf` to add: `host    all    all    127.0.0.1/32    trust`
    - If using password, update `.env` file with your PostgreSQL passwords
3.  **Configure Tenant ID**: Set `TENANT_ID` in the `.env` file to identify your clinic
4.  **Run the FastAPI application** in development mode using the command below. This command will watch for changes and automatically restart the server.

    ```bash
    fastapi dev main.py
    ```

    * You should see a message like: `Serving at: http://127.0.0.1:8000`
    * The application will show database connection status on startup
5.  **Access the documentation** (optional):
    * Open your browser and go to `http://127.0.0.1:8000/docs` to see the **Swagger UI** for testing the API endpoints.

---

## 🗄️ PostgreSQL Setup

### Step-by-Step .env Configuration

The application uses a dual PostgreSQL architecture. Follow these steps to configure your `.env` file:

#### Step 1: Locate or Create the .env File

The `.env` file should be located in the `backend` folder:
```
backend/
  ├── .env          ← This file (will be auto-created on first run)
  ├── app/
  └── ...
```

**If the file doesn't exist**, it will be automatically created when you first run the application. However, you can also create it manually.

#### Step 2: Configure Local PostgreSQL Settings

These settings are for your **local clinic database** (where data is stored first):

```env
# Local PostgreSQL Settings (for each clinic)
LOCAL_POSTGRES_HOST=localhost
LOCAL_POSTGRES_PORT=5433
LOCAL_POSTGRES_USER=postgres
LOCAL_POSTGRES_PASSWORD=your_actual_local_password  # ⚠️ REQUIRED: Replace with your actual password
LOCAL_POSTGRES_DB=clinic_db_local
```

**What to change:**
- `LOCAL_POSTGRES_PASSWORD`: Replace `your_actual_local_password` with your actual PostgreSQL password
- `LOCAL_POSTGRES_PORT`: Change if your PostgreSQL uses a different port (default is 5432, but 5433 is used here)
- `LOCAL_POSTGRES_DB`: You can change the database name if needed

#### Step 3: Configure Main Server PostgreSQL Settings

These settings are for the **centralized main server** (where data is synced):

```env
# Main Server PostgreSQL Settings (centralized server)
MAIN_POSTGRES_HOST=your-main-server.com  # ⚠️ REQUIRED: Replace with your main server hostname or IP
MAIN_POSTGRES_PORT=5432
MAIN_POSTGRES_USER=postgres
MAIN_POSTGRES_PASSWORD=your_actual_main_password  # ⚠️ REQUIRED: Replace with your actual password
MAIN_POSTGRES_DB=clinic_db_main
```

**What to change:**
- `MAIN_POSTGRES_HOST`: Replace `your-main-server.com` with:
  - Your server's IP address (e.g., `192.168.1.100`)
  - Your server's domain name (e.g., `main-server.example.com`)
  - Or `localhost` if testing locally
- `MAIN_POSTGRES_PASSWORD`: Replace with your main server's PostgreSQL password
- `MAIN_POSTGRES_PORT`: Usually 5432, but change if different
- `MAIN_POSTGRES_DB`: Change the database name if needed

#### Step 4: Set Your Tenant ID

The tenant ID uniquely identifies your clinic:

```env
# Tenant ID (unique identifier for each clinic)
TENANT_ID=clinic_001  # ⚠️ REQUIRED: Change to a unique ID for your clinic
```

**What to change:**
- `TENANT_ID`: Replace `clinic_001` with a unique identifier for your clinic, for example:
  - `clinic_001`, `clinic_002`, `clinic_003` (if using sequential numbers)
  - `downtown_clinic`, `uptown_medical_center` (if using descriptive names)
  - `CLINIC_ABC123` (if using codes)
  
  **Important:** Each clinic installation must have a **unique** tenant ID!

#### Complete .env File Example

Here's a complete example of what your `.env` file should look like:

```env
# Local PostgreSQL Settings (for each clinic)
LOCAL_POSTGRES_HOST=localhost
LOCAL_POSTGRES_PORT=5433
LOCAL_POSTGRES_USER=postgres
LOCAL_POSTGRES_PASSWORD=mylocalpass123
LOCAL_POSTGRES_DB=clinic_db_local

# Main Server PostgreSQL Settings (centralized server)
MAIN_POSTGRES_HOST=192.168.1.100
MAIN_POSTGRES_PORT=5432
MAIN_POSTGRES_USER=postgres
MAIN_POSTGRES_PASSWORD=mymainpass456
MAIN_POSTGRES_DB=clinic_db_main

# Tenant ID (unique identifier for each clinic)
TENANT_ID=clinic_001

# Security Settings (optional)
SECRET_KEY=
```

#### Step 5: Save and Verify

1. **Save the file** after making your changes
2. **Verify** that:
   - No spaces around the `=` sign (e.g., `PASSWORD=abc123` not `PASSWORD = abc123`)
   - No quotes around values (unless the value itself contains spaces)
   - All required fields are filled in (passwords and tenant ID)

#### Security Note

⚠️ **Never commit the `.env` file to version control!** It's already in `.gitignore` to prevent accidental commits.

### Architecture

- **Local PostgreSQL**: Stores data for the current clinic. All operations read/write to this database first.
- **Main Server PostgreSQL**: Centralized database that receives synced data from all clinics. Data is separated by `tenant_id`.
- **Synchronization**: Data is automatically synced from Local → Main Server after create/update operations.

### Troubleshooting

#### If connection fails:
1. **Check PostgreSQL service is running:**
   - Open Services (`services.msc`)
   - Find "PostgreSQL" service
   - Right-click → Start (if stopped)

2. **Verify port and password:**
   - Check the port numbers in `.env` file: `LOCAL_POSTGRES_PORT` and `MAIN_POSTGRES_PORT`
   - Check the passwords in `.env` file: `LOCAL_POSTGRES_PASSWORD` and `MAIN_POSTGRES_PASSWORD`
   - Verify `TENANT_ID` is set correctly
   - Make sure these match your PostgreSQL server settings

3. **Restart the application** after changing `.env` file

### Need Help?

The application will show connection status when it starts. If PostgreSQL shows as "NOT CONNECTED", check the error message for details.

---

## 💡 API Endpoints

The API provides the following endpoints for managing patient records:

| HTTP Method | Path | Description |
| :--- | :--- | :--- |
| **GET** | `/` | Welcomes the user to the API. |
| **GET** | `/api/patients/` | Fetches a list of **all patient records**. |
| **POST** | `/api/patients/` | **Creates a new patient record** in the database. |

### Patient Data Model

The data for a new patient must follow this structure, as defined in `schemas.py`:

```python
class Patient(BaseModel):
    # Required Fields
    name: str                    # Patient's full name
    age: int                     # Patient's age (integer, must be > 0)
    gender: str                  # Gender: "male", "female", or "other" (validated)
    phone: str                   # Patient's phone number (must be unique per tenant)
    registration_date: str       # Date of registration
    referral_source: str         # Referral source: "doctor", "self", "friend", or "online" (validated)
    patient_status: str          # Patient status: "Active", "Inactive", "VIP", "Do not treat", or "Requires follow up" (validated)
    billed_amount: float         # Total billed amount (must be >= 0)
    outstanding_amount: float     # Amount still owed (must be >= 0)
    
    # Optional Fields
    id: Optional[int] = None                    # Patient ID (auto-generated, optional on create)
    tenant_id: Optional[str] = None             # Tenant ID (auto-set from settings if not provided)
    email: Optional[str] = None                 # Patient's email address
    date_of_birth: Optional[str] = None         # Date of birth (calendar widget on UI)
    address: Optional[str] = None               # Patient's address
    referral_subcategory: Optional[str] = None  # Optional referral subcategory (e.g., "Dr. Sharma", "Google")
    important_notes: Optional[str] = None        # Optional notes (stored only in local server, NOT synced to main)
    
    # Internal Fields (not required in API requests)
    synced_to_main: Optional[bool] = False      # Sync status (internal)
    last_synced_at: Optional[datetime] = None    # Last sync timestamp (internal)
```

#### Field Validation Rules

- **gender**: Must be exactly one of: `"male"`, `"female"`, or `"other"`
- **referral_source**: Must be exactly one of: `"doctor"`, `"self"`, `"friend"`, or `"online"`
- **patient_status**: Must be exactly one of: `"Active"`, `"Inactive"`, `"VIP"`, `"Do not treat"`, or `"Requires follow up"`
- **phone**: Must be unique per `tenant_id` (each clinic can have its own patient with the same phone number)
- **important_notes**: This field is stored only in the local database and is NOT synced to the main server

#### Example Patient Data

```json
{
  "name": "John Doe",
  "age": 30,
  "gender": "male",
  "phone": "1234567890",
  "email": "john.doe@example.com",
  "date_of_birth": "1994-01-15",
  "address": "123 Main St, City, State 12345",
  "registration_date": "2024-01-15",
  "referral_source": "doctor",
  "referral_subcategory": "Dr. Sharma",
  "patient_status": "Active",
  "important_notes": "Patient prefers morning appointments",
  "billed_amount": 1000.0,
  "outstanding_amount": 500.0
}
```