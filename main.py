#!/usr/bin/env python3

import pandas as pd
import sys
from functools import reduce, cache

spreadsheet = 'IWOL Alchemy and Forging Guide.xlsx'

@cache
def get_recipes():
    names = ['grade', None, 'recipe_name', 'slot', 'quantity', 'herb', None, None, 'potency', 'property']
    data = pd.read_excel(spreadsheet, sheet_name='Recipes', skiprows=2, header=None, usecols='B:K', names=names)

    # Assemble the recipe from the rows that describe each ingredient slot
    recipes = {}
    for ingredient in data.itertuples():
        if ingredient.recipe_name not in recipes:
            recipes[ingredient.recipe_name] = {}

        if isinstance(ingredient.herb, str):
            recipes[ingredient.recipe_name][ingredient.slot] = {
                'quantity': ingredient.quantity,
                'herb': get_herb(name=ingredient.herb)
            }

    return recipes


@cache
def get_herbs():
    data = pd.read_excel(spreadsheet, sheet_name='Herbs', usecols='A:C,E,G')
    return [i for i in data.itertuples() if 'Demon Core' not in i.Name ]


def get_herb(name):
    return next((h for h in get_herbs() if h.Name == name), None)


def count_num_herbs(recipe):
    return reduce(lambda total, slot: total + slot['quantity'], recipe.values(), 0)


def herbs_by(grade=None, property=None):
    return [
        h for h in get_herbs()
        if h.Grade == grade and (
            h.Primary == property or
            h.Secondary == property or
            h.Temperature == property
        )
    ]


def get_balancing_temperature(recipe):
    temperatures = [
        ingredient['herb'].Temperature
        for slot, ingredient in recipe.items() if slot != 'Temperature'
    ]
    if temperatures.count('Cold') > temperatures.count('Heat'):
        return 'Heat'
    elif temperatures.count('Cold') < temperatures.count('Heat'):
        return 'Cold'
    else:
        return 'Balanced'


def sidetier_ingredient(slot, recipe):
    herb = recipe[slot]['herb']
    qty = recipe[slot]['quantity']

    # Drop the number from the slot name when looking up herb property
    property = getattr(herb, slot.split(' ')[0])

    sidetiered_recipe = [
        { **recipe, slot: { 'herb': new_herb, 'quantity': qty } }
        for new_herb in herbs_by(grade=herb.Grade, property=property)
        if new_herb != herb
    ]

    if slot == 'Temperature': # No temperatures have changed
        return sidetiered_recipe

    # Figure out the correct temperature herbs for the sidetiered recipes
    return [ b for r in sidetiered_recipe for b in balance_recipe_temperature(r) ]

def balance_recipe_temperature(recipe):
    herb = recipe['Temperature']['herb']
    qty = recipe['Temperature']['quantity']
    return [
        { **recipe, 'Temperature': { 'herb': h, 'quantity': qty } }
        for h in herbs_by(grade=herb.Grade, property=get_balancing_temperature(recipe))
    ]


def sidetier(recipe, found=[]):
    sidetiered_recipes = []
    recurse_on = []
    for slot in recipe.keys():
        for i, new_recipe in enumerate(sidetier_ingredient(slot, recipe)):
            if i == 0:
                recurse_on.append(new_recipe)
            if new_recipe not in found:
                sidetiered_recipes.append(new_recipe)

    if not sidetiered_recipes:
        return []

    return sidetiered_recipes + [
        j
        for i in recurse_on
        for j in sidetier(i, [recipe] + found + sidetiered_recipes)
    ]


def downtier_ingredient(slot, recipe):
    herb = recipe[slot]['herb']
    qty = recipe[slot]['quantity']

    # Drop the number from the slot name when looking up herb property
    # e.g. 'Primary 2' becomes 'Primary'
    property = getattr(herb, slot.split(' ')[0])

    # T6 herbs can be replaced by 6 T5
    # T5 herbs can be replaced by 5 T4 etc.
    qty_ratio = { 6: 6, 5: 5, 4: 4, 3: 3, 2: 3 }

    downtiered_recipes = [
        { **recipe, slot: { 'herb': new_herb, 'quantity': qty * qty_ratio[herb.Grade] } }
        for new_herb in herbs_by(grade=herb.Grade-1, property=property)
    ]

    if slot == 'Temperature': # No temperatures have changed
        return downtiered_recipes

    # Figure out the correct temperature herbs for the downtiered recipes
    return [ b for r in downtiered_recipes for b in balance_recipe_temperature(r) ]


def downtier(recipe, furnace_capacity=14, found=[]):
    downtiered_recipes = []
    for slot in recipe.keys():
        for i, new_recipe in enumerate(downtier_ingredient(slot, recipe)):
            if count_num_herbs(new_recipe) <= furnace_capacity and new_recipe not in found:
                downtiered_recipes.append(new_recipe)

                # Only recurse on the first of the downtiered recipes for each slot
                # to reduce the number of duplicate recipes generated
                if i == 0:
                    new_additions = downtier(new_recipe, furnace_capacity, [recipe] + found + downtiered_recipes)
                    downtiered_recipes.extend(new_additions)

    return downtiered_recipes

def print_recipe(recipe):
    print(
        'Price: {}\t'.format(calculate_price(recipe)),
        '\t'.join([
            '{}: {:0.0f}x {} '.format(slot, ingredient['quantity'], ingredient['herb'].Name)
            for slot, ingredient in recipe.items()
        ])
    )


def calculate_price(recipe):
    pricing = { 1: 3, 2: 12, 3: 135, 4: 1440, 5: 13500, 6: 81000 }
    return sum([
        pricing[ingredient['herb'].Grade] * ingredient['quantity'] * 2
        for ingredient in recipe.values()
    ])


if __name__ == '__main__':
    name = sys.argv[1]

    recipe = get_recipes()[name]

    print_recipe(recipe)
    for i in sorted(sidetier(recipe) + downtier(recipe), key=calculate_price, reverse=True):
        print_recipe(i)

from unittest import TestCase, skip
class TestRecipes(TestCase):
    def test_that_herbs_can_be_loaded_from_spreadsheet(self):
        herbs = get_herbs()
        self.assertEqual('Azuresky Flower', herbs[0].Name)
        self.assertEqual('Mending', herbs[0].Primary)
        self.assertEqual('Focusing', herbs[0].Secondary)
        self.assertEqual('Heat', herbs[0].Temperature)
        self.assertEqual(1, herbs[0].Grade)

    def test_that_recipes_can_be_loaded_from_spreadsheet(self):
        recipes = get_recipes()
        self.assertEqual({ 'herb': get_herb(name='Waterglade Lily'), 'quantity': 3.0 },
            recipes['Bright Heart Elixir']['Primary'])
        self.assertEqual({ 'herb': get_herb(name='Sepastra Herb'), 'quantity': 4.0 },
            recipes['Bright Heart Elixir']['Secondary'])
        self.assertEqual({ 'herb': get_herb(name='Panacea Dew'), 'quantity': 2.0 },
            recipes['Bright Heart Elixir']['Secondary 2'])
        self.assertEqual({ 'herb': get_herb(name='Panacea Dew'), 'quantity': 1.0 },
            recipes['Bright Heart Elixir']['Temperature'])

    def test_that_herb_can_be_found_by_grade_and_property(self):
        found = herbs_by(grade=4.0, property='Cold')
        self.assertEqual(12, len(found))

    def test_that_the_temperature_of_the_temperature_herb_can_be_calculated(self):
        recipes = get_recipes()
        self.assertEqual('Heat', get_balancing_temperature(recipes['Expert Healing Elixir']))
        self.assertEqual('Cold', get_balancing_temperature(recipes['Divine Heart Elixir']))
        self.assertEqual('Balanced', get_balancing_temperature(recipes['Azure Heart Elixir']))

    def test_that_recipes_can_be_downtiered(self):
        recipes = get_recipes()
        self.assertTrue(len(downtier(recipes['Greater Healing Elixir'])) > 10)

    def test_that_recipes_can_be_sidetiered(self):
        recipes = get_recipes()
        self.assertTrue(len(sidetier(recipes['Greater Healing Elixir'])) > 10)

    def test_that_alternate_recipes_can_be_generate_without_duplicates(self):
        def find_duplicates(candidates):
            found = []
            duplicates = []
            for i in candidates:
                if i not in found:
                    found.append(i)
                elif i not in duplicates:
                    duplicates.append(i)
            return duplicates

        def print_duplicate_recipes(candidates):
            for i in find_duplicates(candidates):
                print_recipe(i)

        recipe = get_recipes()['Wellspring Elixir']
        alternate_recipes = [ i for i in downtier(recipe) + sidetier(recipe) ]
        self.assertFalse(find_duplicates(alternate_recipes))
