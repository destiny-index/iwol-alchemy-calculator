from flask import Flask, request, jsonify, url_for, render_template
from urllib.parse import urlencode
from math import isnan

from main import (
    generate_all_recipes_for,
    recipes_to_sorted_dicts,
    get_elixirs,
    get_recipe_slots,
    only_minimal,
    get_dao_exp
)

app = Flask(__name__)

@app.route('/recipes/<name>')
def recipes(name):
    capacity = request.args.get('capacity', default=14, type=int)
    recipes = only_minimal(generate_all_recipes_for(name, furnace_capacity=capacity))

    elixir = next(e for e in get_elixirs_as_dicts() if e['name'] == name)

    return render_template(
        'recipes.html',
        name=name,
        elixir=elixir,
        capacity=capacity,
        recipes=recipes_to_sorted_dicts(recipes, reverse=False)
    )


@app.route('/')
def home():
    return render_template('index.html', elixirs=get_elixirs_as_dicts())

def get_elixirs_as_dicts():
    return [
        {
            'grade': elixir.grade,
            'type': elixir.type,
            'name': elixir.name,
            'effect': elixir.effect,
            'resistance': elixir.resistance,
            'discovery_exp': get_dao_exp(elixir),
            'exp': int(get_dao_exp(elixir) / 3),
            'price': elixir.value,
            'recipes': url_for('recipes', name=elixir.name)
        }
        for elixir in get_elixirs()
    ]

