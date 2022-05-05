from flask import Flask, request, jsonify, url_for, render_template
from urllib.parse import urlencode
from main import generate_all_recipes_for, recipes_to_sorted_dicts, get_elixirs, get_recipe_slots, only_minimal

app = Flask(__name__)

@app.route('/recipes/<name>')
def recipes(name):
    capacity = request.args.get('capacity', default=14, type=int)
    recipes = only_minimal(generate_all_recipes_for(name, furnace_capacity=capacity))

    return render_template(
        'recipes.html',
        name=name,
        capacity=capacity,
        recipes=recipes_to_sorted_dicts(recipes, reverse=False)
    )

@app.route('/')
def home():
    elixirs = [
        {
            'grade': elixir.grade,
            'type': elixir.type,
            'name': elixir.name,
            'effect': elixir.effect,
            'recipes': url_for('recipes', name=elixir.name)
        }
        for elixir in get_elixirs()
    ]
    return render_template('index.html', elixirs=elixirs)
