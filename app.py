from flask import Flask, request, render_template, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
import openai
from twilio.twiml.messaging_response import MessagingResponse
import os
import logging

# Initialize the Flask app
app = Flask(__name__)

# Configure the database URI and disable modification tracking
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///training_data.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize SQLAlchemy with the Flask app
db = SQLAlchemy(app)

# Initialize Flask-Migrate with the Flask app and SQLAlchemy db
migrate = Migrate(app, db)

# Configure logging
logging.basicConfig(level=logging.INFO)

# Initialize the OpenAI API key from environment variables
openai.api_key = os.environ.get("OPENAI_API_KEY")

# Define the TrainingData model
class TrainingData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question = db.Column(db.String(500), nullable=False)
    answer = db.Column(db.String(500), nullable=False)

    def __repr__(self):
        return f'<TrainingData {self.question}>'

# Initialize the database before the first request
@app.before_first_request
def create_tables():
    db.create_all()

# Function to search for answers in the database
def search_training_data(query):
    results = TrainingData.query.filter(TrainingData.question.ilike(f'%{query}%')).all()
    return results

# Function to generate answers using GPT-3.5-turbo
def generate_answer(question):
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": question}
            ],
            max_tokens=150,
            temperature=0.7,
        )
        answer = response.choices[0].message['content'].strip()
        return answer
    except Exception as e:
        logging.error(f"Error generating answer: {e}")
        return "I'm sorry, I couldn't process your request."

# Route to handle incoming chat requests
@app.route('/chatgpt', methods=['GET', 'POST'])
def chatgpt():
    if request.method == 'POST':
        incoming_que = request.values.get('Body', '').lower()
        logging.info(f"Question: {incoming_que}")

        # Search for the answer in the training data
        results = search_training_data(incoming_que)
        if results:
            answer = results[0].answer
        else:
            # Generate the answer using GPT-3.5-turbo
            answer = generate_answer(incoming_que)

        logging.info(f"BOT Answer: {answer}")

        bot_resp = MessagingResponse()
        msg = bot_resp.message()
        msg.body(answer)
        return str(bot_resp)
    else:
        return "This endpoint is for POST requests from Twilio."

# Route to handle the root URL
@app.route('/', methods=['GET'])
def index():
    return "This is a WhatsApp chatbot powered by GPT-3.5-turbo. Use the /chatgpt endpoint to interact with the bot."

# Route to handle adding new training data
@app.route('/add', methods=['GET', 'POST'])
def add_training_data():
    if request.method == 'POST':
        question = request.form['question']
        answer = request.form['answer']
        new_data = TrainingData(question=question, answer=answer)
        db.session.add(new_data)
        db.session.commit()
        return redirect(url_for('add_training_data'))
    return render_template('add.html')

# Route to view and search the training data
@app.route('/view', methods=['GET', 'POST'])
def view_training_data():
    query = request.args.get('query')
    if query:
        data = search_training_data(query)
    else:
        data = TrainingData.query.all()
    return render_template('view.html', data=data)

# Route to edit training data
@app.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit_training_data(id):
    data = TrainingData.query.get_or_404(id)
    if request.method == 'POST':
        data.question = request.form['question']
        data.answer = request.form['answer']
        db.session.commit()
        return redirect(url_for('view_training_data'))
    return render_template('edit.html', data=data)

# Route to delete training data
@app.route('/delete/<int:id>', methods=['POST'])
def delete_training_data(id):
    data = TrainingData.query.get_or_404(id)
    db.session.delete(data)
    db.session.commit()
    return redirect(url_for('view_training_data'))

# Run the Flask app
if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=False, port=5000)