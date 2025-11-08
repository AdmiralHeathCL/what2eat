# What2Eat? – AI Dinner Recommender

A dinner recommendation tool built with **Django** with *SQLite* and **Yelp Fusion API**.  
It helps users find restaurants by chatting with AI Agent and viewing nearby restaurant suggestions on a live **Leaflet map**.

> *Anywhere’s fine*, she said. Now you are sitting alone at McDonald's right after she broken up with you.*
> 
> Look familiar? Scenes like these are happening all over the galaxy right now. You could be next.
> 
> But with the latest **What2Eat**, no more guesswork, no more heartbreak. 
> 
> Just delicious dinner plans guaranteed to make her say, *Wow, you actually picked this place?*
> 
 Now available at https://what2eat-99tj.onrender.com/

MCP Tool Version: https://github.com/AdmiralHeathCL/what-to-eat-for-dinner

![img_1.png](img_1.png)

---

## Features

- **Real-Time Restaurant Data** – Integrates with the Yelp Fusion API to show live restaurant information.
- **Smart Query Generation** – Transforms user intent into structured Yelp queries including cuisine, price, rating, and distance.
- **Review Summaries** – Fetches short review snippets for top results to give a quick overview of each restaurant.
- **Keyword and Exclusion Filters** – Matches keywords and excludes undesired categories.
- **Interactive Map** – Displays recommended locations on a Leaflet-powered map with clickable details.
- **Dynamic Chat Memory** – Maintains conversation context during each session for personalized recommendations.

---

## Workflow

### 1. User Interaction
Users visit the website and use their own OpenAI API key, and start a chat describing what they feel like eating.  
The chat interface maintains conversation history during the session so GPT can ask clarifying questions, such as cuisine type, budget, and location.

### 2. GPT Query Generation
GPT processes the conversation and produces a structured query in JSON format, including parameters like:
- Location
- Cuisine preferences
- Budget range
- Distance and rating filters
- Keywords and exclusions

If GPT requires more details, it continues the dialogue for follow-up questions.

### 3. Backend Processing
Django receives GPT’s structured query and passes it to the Yelp backend module.  
The backend uses the Yelp Fusion API to find matching restaurants, applies filters, and ranks the results based on rating, distance, and keyword relevance.  
Short review excerpts are fetched for a few top results to enhance the user experience.

### 4. Displaying Results
The backend sends restaurant data to the frontend, where it is updated dynamically  and displayed through:
- **A chat window** showing GPT’s recommendations and explanations.
- **A map view** using Leaflet and OpenStreetMap tiles with clickable restaurant markers.

---

## Setup

### Clone the repository

```bash
git clone https://github.com/AdmiralHeathCL/what2eat.git
cd what2eat
```

### Create a virtual environment

```bash
python -m venv .venv
.\.venv\Scripts\activate  # (Windows)
# or
source .venv/bin/activate  # (macOS/Linux)
```

### Install dependencies
```bash
pip install -r requirements.txt
```

### Create .env file
```bash
YELP_API_KEY=your_yelp_api_key_here
```

### Run migrations and start the server
```bash
python manage.py migrate
python manage.py runserver
```
