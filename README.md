# 🏈 **BetAI – Intelligent Sports Betting Decision Agent**

![made-with-python](https://img.shields.io/badge/Made_with-Python-yellow)


**BetAI** is an interactive AI-powered sports betting assistant that combines:

- Real-time sportsbook odds  
- Live game data from ESPN  
- Machine learning models (moneyline + spread)  
- An agent-based decision engine  
- Kelly-based bankroll optimization  
- Paper trading + history visualization  
---

# 📌 **Table of Contents**

- [About the Project](#about)
- [Quick Start](#quick-start)
- [Setup Details](#setup-details)
- [How to Use](#usage)
- [Project Features](#features)
- [Limitations](#limitations)
- [Future Work](#future-work)
- [Acknowledgements](#acknowledgements)

---

<a id="about"></a>
# **About the Project**

BetAI integrates *AI-driven win probability predictions* with *live odds* to evaluate betting edges in real time.

The system architecture includes:

### **1. Supervised ML Models (Moneyline & Spread)**
Trained on historical NFL data using:

- Logistic Regression  
- Random Forest  
- Naive Bayes  
- Ensemble averaging for stability

### **2. Live Data Aggregation**
- **The Odds API** → sportsbook odds  
- **ESPN Scoreboard** → game status, scores, logos  

### **3. Agent-Based Decision Logic**
For every offer, the agent computes:

- Market implied probability  
- Model probability  
- Expected value (EV)  
- Kelly stake fraction  
- **BET / NO BET** recommendation  

### **4. Streamlit Frontend**
Clean multi-tab interface:

- Scoreboard view  
- Game details with live offers  
- Live odds tab  
- Recommendations  
- Open bets  
- History & bankroll performance  

---

<a id="quick-start"></a>
# 🚀 **Quick Start (Mac)**

### **1. Clone the repository**
```bash
git clone https://github.com/krmiller678/BetAI.git
cd BetAI
```

### **2. Run the environment setup script**
```bash
./scripts/setup.sh
```

This will:

✔ Create a virtual environment  
✔ Install all dependencies  
✔ Install the Odds API SDK  
✔ Create your `.env` file  
✔ Train all ML models from scratch  
✔ Prepare all directories  

### **3. Add your Odds API key**

Open `.env` and set:

```
ODDS_API_KEY=your_key_here
```

### **4. Launch the application**
```bash
./scripts/run.sh
```

Your browser will open at:

👉 http://localhost:8501

---

<a id="setup-details"></a>
# ⚙️ **Setup Details**

The setup script handles:

- Python environment creation  
- Fixing or reinstalling pip when necessary  
- Installing ``requirements.txt``  
- Installing the included `odds-sdk` package  
- Creating the environment file  
- Training all ML models automatically  
- Creating standardized project folders  

No manual steps are required beyond inserting your API key.

---

<a id="usage"></a>
# 📈 **How to Use BetAI**

Once the app is running, the UI provides several tabs:

---

## **🏟️ Scoreboard**
- View all games for a selected date  
- Shows team logos, scores, game status  
- Jump into game details  

---

## **📊 Game Details**
- Live team stats  
- All odds from all bookmakers  
- Evaluate or paper-trade any offer  
- Automatic model predictions displayed  

---

## **🔥 Live Odds**
- Odds aggregated across all games  
- Quick evaluate/place buttons  
- Sorted by market (Moneyline, Spread)

---

## **🧠 Recommendations**
Shows the model’s most recent evaluations and EVs.

---

## **💼 Open Bets**
- Shows active paper trades  
- Manual settlement controls  

---

## **📜 History + Graphs**
Visualizes:

- Bankroll performance  
- Profit/loss curves  
- Win/loss statistics  

---

<a id="features"></a>
# ⭐ **Project Features**

### ✔ AI/ML Model Predictions
- Moneyline probability  
- Spread cover probability  
- Ensemble averaging  

### ✔ Agent-Based Decision Making
- Model probability vs implied probability  
- Expected value (EV) calculation  
- Fractional Kelly stake sizing  
- Final BET/NO BET decision  

### ✔ Paper Trading Simulation
- Bankroll tracking  
- Bet placement  
- Manual bet settlement  
- Historical results with graphs  

### ✔ Real-Time Data Integration
- Odds from The Odds API  
- Scores + game metadata from ESPN  
- Full game ID linking logic  

### ✔ Modern Streamlit Frontend
- Fully interactive UI  
- Multi-tab layout  
- Lightweight and runs locally  

---

<a id="limitations"></a>
# ⚠️ **Limitations**

- Bets must be settled manually  
- No persistent data storage outside session state  
- No login system or cloud deployment  
- No in-game ML models (pregame only)  
- Must run locally  
- Models retrain only during setup  

---

<a id="future-work"></a>
# 🔮 **Future Work**

- Automated bet settlement  
- Persistent database + user accounts  
- Cloud deployment  
- In-game predictive modeling  
- Reinforcement learning agents  
- Automated retraining pipeline  
- Multi-sport expansion  

---

<a id="acknowledgements"></a>
# 🙏 **Acknowledgements**

- **Streamlit** — UI framework  
- **scikit-learn** — ML toolkit  
- **Plotly** — visual analytics  
- **The Odds API** — sportsbook integration  
- **ESPN Scoreboard** — game data  

---

# 🎉 **BetAI — AI-Driven Sports Predictions, Done Right.**