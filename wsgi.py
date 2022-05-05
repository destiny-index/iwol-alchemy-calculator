from flask import Flask, request, jsonify
from main import generate_all_recipes_for, recipes_to_sorted_dicts

app = Flask(__name__)

@app.route('/api/recipes')
def read_recipes():
    name = request.args.get('name')
    recipes = generate_all_recipes_for(name)

    return jsonify(recipes_to_sorted_dicts(recipes))
