# Smart Food Waste Management Platform

A web application built with **Streamlit** and **SQLite** that connects food providers with receivers to reduce food waste and promote sustainability.
---

## 🚀 Features

### 🔐 Authentication
- Role-based login system (Provider, Receiver, Admin).
- Secure password hashing.

### 🍴 Provider Dashboard
- Add surplus food listings with details (type, quantity, expiry date, city, meal type).
- View all listings created by the provider.

### 📥 Receiver Dashboard
- Search and filter food listings (by city, food type, meal type).
- Claim food items and track claims in **My Claims**.
- Claim status: Pending, Approved, Rejected, Completed.

### ⚙️ Admin Dashboard
- Manage CRUD operations (create, read, update, delete listings).
- Approve/reject/complete claims.
- View reports & analytics (food saved, provider activity, receiver demand).

### 👤 Profile Page
- View personal profile (Provider/Receiver/Admin).
- Profile button and Logout accessible from top-right header bar.

---

## 🛠️ Tech Stack

- **Frontend/Backend**: [Streamlit](https://streamlit.io/)  
- **Database**: SQLite3  
- **Language**: Python 3.9+  
- **Libraries**: Pandas, hashlib (for password hashing)  

---

## ⚙️ Installation & Setup

### 1. Clone the repository
```bash
git clone https://github.com/your-username/food-waste-platform.git
cd food-waste-platform
