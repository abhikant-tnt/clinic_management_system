# 🏥 Patient API Backend

This is a simple **FastAPI** backend for managing patient records, using **MongoDB** as the database.

---

## 🚀 Getting Started

Follow these steps to set up and run the Patient API on your local machine.

### 📋 Prerequisites

You need the following installed:

1.  **Python 3.x**
2.  **MongoDB Server**: The application connects to a MongoDB server running locally on the default port (`27017`). Make sure it is installed and running.

### 🛠️ Installation

1.  **Clone or download** this project folder.
2.  **Navigate** to the project directory in your terminal.
3.  **Install the required Python packages**:

    ```bash
    pip install -r requirements.txt
    ```

### ▶️ Running the Server

1.  **Start the MongoDB server** (if it's not already running).
2.  **Run the FastAPI application** in development mode using the command below. This command will watch for changes and automatically restart the server.

    ```bash
    fastapi dev main.py
    ```

    * You should see a message like: `Serving at: http://127.0.0.1:8000`
3.  **Access the documentation** (optional):
    * Open your browser and go to `http://127.0.0.1:8000/docs` to see the **Swagger UI** for testing the API endpoints.

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