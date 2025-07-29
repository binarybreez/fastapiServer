# FastAPI Backend Server

This repository contains a FastAPI backend server that powers a job-matching system. It handles resume parsing, user and employer creation, and job posting automation using parsed job descriptions. The application leverages MongoDB for data storage, PyPDF2 for PDF parsing, and Clerk for authentication and user management.

---

## 📁 Project Structure

```
fastapi/
├── app/
│   ├── controllers/         # Business logic and operations
│   ├── models/              # Pydantic models and DB schemas
│   ├── routes/              # API routes
│   ├── utils/               # Utility functions and helpers
│   ├── db.py                # MongoDB database connection
│   └── main.py              # FastAPI app entry point
├── public/                  # Folder for uploaded resumes and public files
├── .env                     # Environment variables
└── README.md                # Project documentation
```

---

## 🚀 Features

- FastAPI-based backend server
- MongoDB integration for persistent storage
- Resume parsing with PyPDF2
- Automatic user and employer creation upon resume upload
- Job creation based on parsed job descriptions
- User authentication with Clerk
- Environment-based configuration via `.env` file
- Organized and modular architecture

---

## 🧰 Tech Stack

- **Backend Framework**: FastAPI
- **Database**: MongoDB
- **PDF Parsing**: PyPDF2
- **Authentication**: Clerk
- **Server**: Uvicorn (ASGI server)

---

## 📦 Installation

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/fastapi.git
cd fastapi
```

### 2. Create a Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows use: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

---

## 🔐 Environment Variables

Create a `.env` file in the project root with the following environment variables:

```
CLERK_API_KEY=your_clerk_api_key
MONGODB_URI=your_mongodb_uri
SECRET_KEY=your_secret_key
```

You may add other variables as needed by your utilities or third-party services.

---

## ▶️ Running the Server

Run the development server using Uvicorn:

```bash
uvicorn app.main:app --reload
```

The server will start at: [http://localhost:8000](http://localhost:8000)

---

## 📤 Resume Upload Flow

1. User uploads a resume (PDF format) to the `/upload-resume` endpoint.
2. The PDF is parsed using **PyPDF2** to extract relevant user and employer information.
3. A new user is created automatically using **Clerk**.
4. An associated employer profile is created and stored in **MongoDB**.
5. Resume files are stored in the `public/` folder.

---

## 📝 Job Description Upload Flow

1. A job description file is uploaded or job details are submitted via API.
2. Job details are parsed to extract structured information.
3. A new job entry is created and stored in **MongoDB**.

---

## 🔗 API Endpoints (Examples)

These are sample routes; actual routes may differ based on implementation:

| Method | Endpoint                  | Description                          |
|--------|---------------------------|--------------------------------------|
| POST   | `/upload-resume`          | Upload resume and create user        |
| POST   | `/upload-job-description` | Upload job description and create job |
| GET    | `/jobs`                   | List all available jobs              |
| GET    | `/users/{user_id}`        | Retrieve user details                |

For complete API reference, see `/docs` (FastAPI's built-in Swagger UI).

---


## 🚧 Deployment

> ⚠️ The server is **not deployed** yet.

Once ready for deployment, you may consider using:

- Docker & Docker Compose
- Cloud services like AWS, GCP, or Heroku
- CI/CD with GitHub Actions or similar tools

---

## 🛠️ Future Improvements

- [ ] Add Docker support
- [ ] Implement CI/CD pipeline
- [ ] Add test coverage
- [ ] Add file size & type validation
- [ ] Rate limit sensitive endpoints
- [ ] Add email notifications for new users

---

## 🤝 Contributing

Contributions are welcome! Please fork the repository and create a pull request with your changes.

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).

---

## 🙏 Acknowledgements

- [FastAPI](https://fastapi.tiangolo.com/)
- [PyPDF2](https://pypi.org/project/PyPDF2/)
- [MongoDB](https://www.mongodb.com/)
- [Clerk](https://clerk.dev/)
- [Uvicorn](https://www.uvicorn.org/)

---
