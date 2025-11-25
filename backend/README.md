# 🏥 Patient API Backend

This is a **FastAPI** backend for managing patient records, using **PostgreSQL** as the primary database and **MongoDB** as a backup/sync database.

---

## 🚀 Getting Started

Follow these steps to set up and run the Patient API on your local machine.

### 📋 Prerequisites

You need the following installed:

1.  **Python 3.x**
2.  **MongoDB Server**: The application connects to a MongoDB server running locally on the default port (`27017`). Make sure it is installed and running.
3.  **PostgreSQL**: The application uses PostgreSQL as the primary database. Make sure PostgreSQL is installed and running.

### 🛠️ Installation

1.  **Clone or download** this project folder.
2.  **Navigate** to the project directory in your terminal.
3.  **Install the required Python packages**:

    ```bash
    pip install -r requirements.txt
    ```

4.  **Generate Prisma Client** (optional, for better type safety):

    First, fetch the required binaries:
    ```bash
    python -m prisma py fetch
    ```

    Then generate the client:
    ```bash
    python -m prisma py generate
    ```

    **Note:** If Prisma generation fails, the application will automatically fall back to raw SQL queries. The app works fine without Prisma - it's optional but recommended for better type safety.

### ▶️ Running the Server

1.  **Start the MongoDB server** (if it's not already running).
2.  **Start the PostgreSQL server** (if it's not already running).
3.  **Configure PostgreSQL** (Optional - for password-free connection):
    - Run the setup script to enable password-free local connections:
      ```bash
      python app/core/setup_postgres_trust.py
      ```
    - Or manually configure `pg_hba.conf` to add: `host    all    all    127.0.0.1/32    trust`
    - If using password, update `.env` file with your PostgreSQL password
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

### Configuration

The application uses PostgreSQL with password authentication. Connection settings are configured in the `.env` file:

1. The `.env` file is automatically created on first run with default settings
2. **IMPORTANT:** You must set your PostgreSQL password in the `.env` file before running the application
3. Update the `.env` file in the `backend` folder:
   ```
   POSTGRES_HOST=localhost
   POSTGRES_PORT=5433
   POSTGRES_USER=postgres
   POSTGRES_PASSWORD=your_actual_password_here  # REQUIRED: Set your PostgreSQL password
   POSTGRES_DB=clinic_db
   ```
4. **Security Note:** Never commit the `.env` file to version control. It's already in `.gitignore`

### Troubleshooting

#### If connection fails:
1. **Check PostgreSQL service is running:**
   - Open Services (`services.msc`)
   - Find "PostgreSQL" service
   - Right-click → Start (if stopped)

2. **Verify port and password:**
   - Check the port number in `.env` file: `POSTGRES_PORT=5433`
   - Check the password in `.env` file: `POSTGRES_PASSWORD=your_password`
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

The data for a new patient must follow this structure, as defined in `models.py`:

```python
class Patient(BaseModel):
    name: str             # Patient's full name (string)
    age: int              # Patient's age (integer, must be > 0)
    phone: str            # Patient's phone number (string, must be unique)
    registration_date: str# Date of registration (string)
    billed_amount: float  # Total billed amount (number, must be >= 0)
    outstanding_amount: float # Amount still owed (number, must be >= 0)