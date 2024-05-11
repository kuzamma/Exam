# Import necessary libraries
from flask import Flask, request, jsonify, render_template, session, redirect, url_for
import psycopg2
import random
import numpy as np
from werkzeug.security import generate_password_hash, check_password_hash




# Initialize Flask app
app = Flask(__name__)
app.secret_key = b'_5#y2L"F4Q8z\n\xec]/'  # secret key for session management

# Connect to PostgreSQL database
conn = psycopg2.connect(
    dbname="postgres",
    user="postgres",
    password="thesis101",
    host="localhost",
    port="5432"
)

@app.route('/')
def home():
    return redirect('/login')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        full_name = request.form['full_name']
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']  
        cursor = conn.cursor()
        cursor.execute("INSERT INTO students (id, full_name, username, password, email) VALUES (DEFAULT, %s, %s, %s, %s)", (full_name, username, password, email))

        conn.commit()
        cursor.close()
        return redirect('/login')
    return render_template('signup.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM students WHERE username = %s AND password = %s", (username, password))
        user = cursor.fetchone()
        cursor.close()
        if user:
            session['username'] = username
            return redirect('/dashboard')
        else:
            return "Invalid username or password"
    return render_template('login.html')





# Function to fetch questions from the database
def fetch_questions(level):
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM questions WHERE level = %s", (level,))
    questions = cursor.fetchall()
    random.shuffle(questions)  # Shuffle the questions
    cursor.close()
    return questions

# Function to calculate scores based on user answers
def calculate_scores(questions, user_answers):
    total_correct = 0
    correct_per_subtopic = {}

    for question_id, selected_option in user_answers.items():
        if '_' in question_id:
            question = next((q for q in questions if q[0] == int(question_id.split('_')[1])), None)
            if question and question[5] == selected_option[0]:  # Correct answer is the last column
                total_correct += 1
                if question[2] not in correct_per_subtopic:
                    correct_per_subtopic[question[2]] = 1
                else:
                    correct_per_subtopic[question[2]] += 1

    return total_correct, correct_per_subtopic

# Function to recommend the lowest scoring subtopic
def recommend_subtopic(correct_per_subtopic):
    lowest_subtopic = min(correct_per_subtopic, key=correct_per_subtopic.get)
    return lowest_subtopic

def genetic_algorithm(correct_per_subtopic):
    population = list(correct_per_subtopic.keys())
    population_size = len(population)
    
    fitness = {individual: correct_per_subtopic.get(individual, 0) for individual in population}
    
    num_generations = 100
    for generation in range(num_generations):
        selected = []
        for _ in range(population_size):
            tournament_size = min(2, population_size)  # Ensure tournament size does not exceed population size
            competitors = random.sample(population, tournament_size)
            winner = max(competitors, key=lambda x: fitness[x])
            selected.append(winner)
        
        crossover_rate = 0.8
        for i in range(0, population_size, 2):
            if i + 1 < len(selected):  # Check if there are enough elements in selected for crossover
                if random.random() < crossover_rate:
                    crossover_point = random.randint(1, len(population[0]) - 1)
                    parent1, parent2 = selected[i], selected[i + 1]
                    child1 = parent1[:crossover_point] + parent2[crossover_point:]
                    child2 = parent2[:crossover_point] + parent1[crossover_point:]
                    selected[i] = child1
                    selected[i + 1] = child2
        
        mutation_rate = 0.1
        for i in range(population_size):
            if random.random() < mutation_rate:
                mutated_index = random.randint(0, len(selected[i]) - 1)
                mutated_gene = random.choice(population)
                selected[i] = selected[i][:mutated_index] + mutated_gene[mutated_index] + selected[i][mutated_index + 1:]
        
        population = selected
        
        fitness = {individual: correct_per_subtopic.get(individual, 0) for individual in population}
    
    lowest_subtopic = min(fitness, key=fitness.get)
    return lowest_subtopic




# Route for evaluating the quiz based on user answers
@app.route('/quiz/evaluate', methods=['POST'])
def evaluate_quiz():
    user_answers = request.form.to_dict(flat=False)
    level = user_answers['level'][0]  # Extract level from form data
    questions = fetch_questions(level)
    total_correct, correct_per_subtopic = calculate_scores(questions, user_answers)
    lowest_subtopic = recommend_subtopic(correct_per_subtopic)
    
    # Run genetic algorithm to potentially find a better recommendation
    genetic_lowest_subtopic = genetic_algorithm(correct_per_subtopic)
    
    # If genetic algorithm suggests a lower scoring subtopic, use it
    if genetic_lowest_subtopic in correct_per_subtopic and correct_per_subtopic[genetic_lowest_subtopic] < correct_per_subtopic.get(lowest_subtopic, float('inf')):
        lowest_subtopic = genetic_lowest_subtopic
    
    # Create a dictionary with only the lowest scoring subtopic
    lowest_score = {lowest_subtopic: correct_per_subtopic.get(lowest_subtopic, 0)}
    
        
    return jsonify({
        'total_correct': total_correct,
        'lowest_score': lowest_score,
        'recommended_subtopic': lowest_subtopic
    })

# Route for running the genetic algorithm to find the lowest scoring subtopic
@app.route('/quiz/genetic-algorithm', methods=['GET'])
def run_genetic_algorithm():
    level = request.args.get('level')
    questions = fetch_questions(level)
    _, correct_per_subtopic = calculate_scores(questions, {})
    
    lowest_subtopic = genetic_algorithm(correct_per_subtopic)
    return jsonify({'lowest_subtopic': lowest_subtopic})


# Route for the dashboard (protected route)
@app.route('/dashboard', methods=['GET'])
def dashboard():
    if 'username' in session:
        username = session['username']
        cursor = conn.cursor()
        cursor.execute("SELECT full_name FROM students WHERE username = %s", (username,))
        full_name = cursor.fetchone()[0]  # Fetch the full name from the database
        cursor.close()
        return render_template('dashboard.html', username=username, full_name=full_name)
    else:
        return redirect(url_for('login'))


# Logout route
@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

@app.route('/r')
def r():
    return render_template('r.html')


# Route for rendering the easy quiz page
@app.route('/easy-quiz', methods=['GET'])
def easy_quiz():
    questions = fetch_questions('easy')
    return render_template('easy.html', questions=questions)

# Route for rendering the moderate quiz page
@app.route('/moderate-quiz', methods=['GET'])
def moderate_quiz():
    questions = fetch_questions('moderate')
    return render_template('moderate.html', questions=questions)

@app.route('/hard-quiz', methods=['GET'])
def hard_quiz():
    questions = fetch_questions('hard')
    return render_template('hard.html', questions=questions)

# Run the Flask app
if __name__ == "__main__":
    app.run(debug=True)
