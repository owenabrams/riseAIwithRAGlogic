from flask import Flask, request, render_template, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
import openai
from twilio.twiml.messaging_response import MessagingResponse
import os
import logging
from werkzeug.utils import secure_filename



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

# Directory to save uploaded files
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Ensure the upload directory exists
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Define the TrainingData model
class TrainingData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question = db.Column(db.String(500), nullable=False)
    answer = db.Column(db.String(500), nullable=False)
    link = db.Column(db.String(500), nullable=True)
    video = db.Column(db.String(500), nullable=True)
    picture = db.Column(db.String(500), nullable=True)
    document = db.Column(db.String(500), nullable=True)

    def __repr__(self):
        return f'<TrainingData {self.question}>'

# Initialize the database before the first request
@app.before_first_request
def create_tables():
    db.create_all()

# Function to search for answers in the database
def search_training_data(query):
    results = TrainingData.query.filter(TrainingData.question.ilike(f'%{query}%')).all()
    logging.info(f"Database search results: {results}")
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
        logging.info(f"Received question: {incoming_que}")

        # Search for the answer in the training data
        results = search_training_data(incoming_que)
        if results:
            answer = results[0].answer
            logging.info(f"Answer found in training data: {answer}")
        else:
            # Generate the answer using GPT-3.5-turbo
            answer = generate_answer(incoming_que)
            logging.info(f"Generated answer using GPT-3.5-turbo: {answer}")

        bot_resp = MessagingResponse()
        msg = bot_resp.message()
        msg.body(answer)
        logging.info(f"Sending response: {answer}")
        return str(bot_resp)
    else:
        return "This endpoint is for POST requests from Twilio"

# Route to handle the root URL
@app.route('/', methods=['GET'])
def index():
    return "This is a WhatsApp chatbot powered by GPT-3.5-turbo. Use the /chatgpt endpoint to interact with the bot."

# Route to handle adding new training data
@app.route('/add', methods=['GET', 'POST'])
def add_training_data():
    if request.method == 'POST':
        try:
            question = request.form['question']
            answer = request.form['answer']
            link = request.form.get('link')
            video = request.form.get('video')
            picture_path = None
            document_path = None

            if 'picture' in request.files:
                picture = request.files['picture']
                if picture and allowed_file(picture.filename):
                    picture_filename = secure_filename(picture.filename)
                    picture.save(os.path.join(app.config['UPLOAD_FOLDER'], picture_filename))
                    picture_path = os.path.join(app.config['UPLOAD_FOLDER'], picture_filename)

            if 'document' in request.files:
                document = request.files['document']
                if document and allowed_file(document.filename):
                    document_filename = secure_filename(document.filename)
                    document.save(os.path.join(app.config['UPLOAD_FOLDER'], document_filename))
                    document_path = os.path.join(app.config['UPLOAD_FOLDER'], document_filename)

            new_data = TrainingData(question=question, answer=answer, link=link, video=video, picture=picture_path, document=document_path)
            db.session.add(new_data)
            db.session.commit()
            return redirect(url_for('add_training_data'))
        except Exception as e:
            logging.error(f"Error adding training data: {e}")
            return "An error occurred while adding the training data."
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
        try:
            data.question = request.form['question']
            data.answer = request.form['answer']
            data.link = request.form.get('link')
            data.video = request.form.get('video')

            if 'picture' in request.files:
                picture = request.files['picture']
                if picture and allowed_file(picture.filename):
                    picture_filename = secure_filename(picture.filename)
                    picture.save(os.path.join(app.config['UPLOAD_FOLDER'], picture_filename))
                    data.picture = os.path.join(app.config['UPLOAD_FOLDER'], picture_filename)

            if 'document' in request.files:
                document = request.files['document']
                if document and allowed_file(document.filename):
                    document_filename = secure_filename(document.filename)
                    document.save(os.path.join(app.config['UPLOAD_FOLDER'], document_filename))
                    data.document = os.path.join(app.config['UPLOAD_FOLDER'], document_filename)

            db.session.commit()
            return redirect(url_for('view_training_data'))
        except Exception as e:
            logging.error(f"Error updating data: {e}")
            return "An error occurred while updating the data."

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
