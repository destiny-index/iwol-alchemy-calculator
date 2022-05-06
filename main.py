#!/usr/bin/env python3

import pandas as pd
import sys
import json
from functools import reduce, cache

alchemy_guide = 'IWOL Alchemy and Forging Guide.xlsx'
item_list = 'IWOL_Item_Steam_Build_8574886.xlsx'

@cache
def get_elixirs():
    names = ['grade', 'name', 'type', 'toxicity', 'resistance']
    elixirs = pd.read_excel(alchemy_guide, sheet_name='Elixirs', usecols='A:C,E:F', names=names)

    names = ['name', 'value', 'effect', 'description']
    items = pd.read_excel(item_list, sheet_name='d_items py datas', usecols='E,S:U', names=names)

    data = elixirs.merge(items, on='name', how='left')
    return [i for i in data.itertuples()]

@cache
def get_recipes():
    names = ['grade', None, 'recipe_name', 'slot', 'quantity', 'herb', None, None, 'potency', 'property']
    data = pd.read_excel(alchemy_guide, sheet_name='Recipes', skiprows=2, header=None, usecols='B:K', names=names)

    # Assemble the recipe from the rows that describe each ingredient slot
    recipes = {}
    for ingredient in data.itertuples():
        # Fix bugged recipe name
        recipe_name = ingredient.recipe_name if ingredient.recipe_name != 'Battle - Soul Sense' else 'Eclipse Moon Strong Soul Pill'

        if recipe_name not in recipes:
            recipes[recipe_name] = { 'name': recipe_name }

        if isinstance(ingredient.herb, str):
            recipes[recipe_name][ingredient.slot] = {
                'quantity': ingredient.quantity,
                'herb': get_herb(name=ingredient.herb)
            }

    return recipes

@cache
def get_herbs():
    names = ['name', 'value', 'effect', 'description']
    items = pd.read_excel(item_list, sheet_name='d_items py datas', usecols='E,S:U', names=names)

    names = ['grade', 'name', 'primary', 'secondary', 'temperature']
    data = pd.read_excel(alchemy_guide, sheet_name='Herbs', usecols='A:C,E,G', names=names)
    return [i for i in data.itertuples() if 'Demon Core' not in i.name ]


def get_herb(name):
    return next((h for h in get_herbs() if h.name == name), None)


def get_elixir(name):
    return next((e for e in get_elixirs() if e.name == name), None)


def count_num_herbs(recipe):
    return reduce(lambda total, slot: total + recipe[slot]['quantity'], get_recipe_slots(recipe), 0)


def herbs_by(grade=None, property=None):
    to_avoid = [
        'Bloodrend Pearl',
        'Soulrend Pearl',
        'Blood Bodhi Fruit',
        'Crystalized Soul',
        'Dragon\'s Whiskers Vine',
        'Netherrealm Bone',
        'Royal Dragon Flower',
        'Nine Dragons Deep Aloe',
    ]
    return [
        h for h in get_herbs()
        if h.grade == grade and h.name not in to_avoid and (
            h.primary == property or
            h.secondary == property or
            h.temperature == property
        )
    ]


def get_balancing_temperature(recipe):
    temperatures = [
        recipe[slot]['herb'].temperature
        for slot in get_recipe_slots(recipe) if slot != 'Temperature'
    ]
    if temperatures.count('Cold') > temperatures.count('Heat'):
        return 'Heat'
    elif temperatures.count('Cold') < temperatures.count('Heat'):
        return 'Cold'
    else:
        return 'Balanced'


def is_slot_splittable(slot, recipe, furnace_capacity):
    return (
        (slot == 'Primary' and 'Primary 2' not in recipe and furnace_capacity == 14) or
        (slot == 'Secondary' and 'Secondary 2' not in recipe and furnace_capacity > 9)
    )

def get_fixed_herb_property(herb, slot):
    # Drop the number from the slot name when looking up herb property
    property = getattr(herb, slot.lower().split(' ')[0])

    return property


def sidetier_ingredient(slot, recipe, furnace_capacity):
    herb = recipe[slot]['herb']
    qty = recipe[slot]['quantity']
    property = get_fixed_herb_property(herb, slot)

    sidetiered_recipes = [
        { **recipe, slot: { 'herb': new_herb, 'quantity': qty } }
        for new_herb in herbs_by(grade=herb.grade, property=property)
        if new_herb != herb
    ]

    if is_slot_splittable(slot, recipe, furnace_capacity):
        split_slot_recipes = [
            {
                **recipe,
                slot: { 'herb': j[slot]['herb'], 'quantity': qty - i },
                slot + ' 2': { 'herb': j[slot]['herb'], 'quantity': i }
            }
            for i in range(1, int(qty))
            for j in sidetiered_recipes + [recipe]
        ]
        sidetiered_recipes.extend(split_slot_recipes)

    if slot == 'Temperature': # No temperatures have changed
        return sidetiered_recipes

    # Figure out the correct temperature herbs for the sidetiered recipes
    return [ b for r in sidetiered_recipes for b in balance_recipe_temperature(r) ]

def balance_recipe_temperature(recipe):
    herb = recipe['Temperature']['herb']
    qty = recipe['Temperature']['quantity']
    return [
        { **recipe, 'Temperature': { 'herb': h, 'quantity': qty } }
        for h in herbs_by(grade=herb.grade, property=get_balancing_temperature(recipe))
    ]


def get_recipe_slots(recipe):
    possible_slots = [ 'Primary', 'Primary 2', 'Secondary', 'Secondary 2', 'Temperature' ]
    return [ slot for slot in possible_slots if slot in recipe.keys()]


def sidetier(recipe, furnace_capacity=14, found=[]):
    sidetiered_recipes = []
    recurse_on = []
    for slot in get_recipe_slots(recipe):
        for i, new_recipe in enumerate(sidetier_ingredient(slot, recipe, furnace_capacity)):
            if i == 0:
                recurse_on.append(new_recipe)
            if new_recipe not in found:
                sidetiered_recipes.append(new_recipe)

    if not sidetiered_recipes:
        return []

    return sidetiered_recipes + [
        j
        for i in recurse_on
        for j in sidetier(i, furnace_capacity, [recipe] + found + sidetiered_recipes)
    ]


def downtier_ingredient(slot, recipe):
    herb = recipe[slot]['herb']
    qty = recipe[slot]['quantity']
    property = get_fixed_herb_property(herb, slot)

    # T6 herbs can be replaced by 6 T5
    # T5 herbs can be replaced by 5 T4 etc.
    qty_ratio = { 6: 6, 5: 5, 4: 4, 3: 3, 2: 3 }

    downtiered_recipes = [
        { **recipe, slot: { 'herb': new_herb, 'quantity': qty * qty_ratio[herb.grade] } }
        for new_herb in herbs_by(grade=herb.grade-1, property=property)
    ]

    if slot == 'Temperature': # No temperatures have changed
        return downtiered_recipes

    # Figure out the correct temperature herbs for the downtiered recipes
    return [ b for r in downtiered_recipes for b in balance_recipe_temperature(r) ]


def downtier(recipe, furnace_capacity=14, found=[]):
    downtiered_recipes = []
    for slot in get_recipe_slots(recipe):
        for i, new_recipe in enumerate(downtier_ingredient(slot, recipe)):
            if count_num_herbs(new_recipe) <= furnace_capacity and new_recipe not in found:
                downtiered_recipes.append(new_recipe)

                # Only recurse on the first of the downtiered recipes for each slot
                # to reduce the number of duplicate recipes generated
                if i == 0:
                    new_additions = downtier(new_recipe, furnace_capacity, [recipe] + found + downtiered_recipes)
                    downtiered_recipes.extend(new_additions)

    return downtiered_recipes


def uptier(recipe, furnace_capacity=14, found=[]):
    uptiered = []
    for slot in get_recipe_slots(recipe):
        for i, new_recipe in enumerate(uptier_ingredient(slot, recipe, furnace_capacity)):
            if new_recipe not in found and new_recipe not in uptiered:
                uptiered.append(new_recipe)

                if i == 0:
                    new_additions = uptier(new_recipe, furnace_capacity, [recipe] + found + uptiered)
                    uptiered.extend(new_additions)

    return uptiered


def uptier_ingredient(slot, recipe, furnace_capacity=14):
    herb = recipe[slot]['herb']
    qty = recipe[slot]['quantity']
    property = get_fixed_herb_property(herb, slot)

    # T6 herbs can be replaced by 6 T5
    # T5 herbs can be replaced by 5 T4 etc.
    qty_ratio = { 6: 6, 5: 5, 4: 4, 3: 3, 2: 3 }

    if herb.grade < 6 and qty % qty_ratio[herb.grade+1] != 0:
        return []

    uptiered_recipes = [
        { **recipe, slot: { 'herb': h, 'quantity': qty / qty_ratio[h.grade] } }
        for h in herbs_by(grade=herb.grade+1, property=property)
    ]

    if slot == 'Temperature':
        return uptiered_recipes

    return [ b for r in uptiered_recipes for b in balance_recipe_temperature(r) ]


def calculate_slots(recipe):
    return len(recipe.items())

def calculate_herb_types(recipe):
    herbs = []
    for slot in get_recipe_slots(recipe):
        if recipe[slot]['herb'] not in herbs:
            herbs.append(recipe[slot]['herb'])
    return len(herbs)

def calculate_value(recipe):
    elixir = get_elixir(recipe['name'])
    return elixir.value if elixir else None


def herb_to_dict(herb, slot):
    return {
        'name': herb.name,
        'grade': 'T{:0.0f}'.format(herb.grade),
        'property': get_fixed_herb_property(herb, slot) if slot != 'Temperature' else None,
        'temperature': get_fixed_herb_property(herb, 'Temperature'),
    }

def recipe_to_dict(recipe):
    as_dict = {
        slot.lower().replace(' ', ''): {
            'quantity': int(recipe[slot]['quantity']),
            **herb_to_dict(recipe[slot]['herb'], slot)
        }
        for slot in get_recipe_slots(recipe)
    }
    return {
        'name': recipe['name'],
        **as_dict,
        'cost': int(calculate_cost(recipe)),
        'value': int(calculate_value(recipe)),
        'exp': int(get_dao_exp(get_elixir(recipe['name'])) / 3),
        'profit': int(calculate_value(recipe) - calculate_cost(recipe))
    }


def print_recipe(recipe):
    print(json.dumps(recipe_to_dict(recipe), indent=2))


def sort_recipes(recipes, reverse=True):
    criteria = lambda r: (calculate_cost(r), calculate_herb_types(r), calculate_slots(r))
    return sorted(recipes, key=criteria, reverse=reverse)


def recipes_to_sorted_dicts(recipes, reverse=True):
    return [ recipe_to_dict(recipe) for recipe in sort_recipes(recipes, reverse) ]


def print_recipes(recipes):
    result = recipes_to_sorted_dicts(recipes)
    print(json.dumps(result, indent=2))


def calculate_cost(recipe):
    pricing = { 1: 3, 2: 12, 3: 135, 4: 1440, 5: 13500, 6: 81000 }
    return sum([
        pricing[recipe[slot]['herb'].grade] * recipe[slot]['quantity'] * 2
        for slot in get_recipe_slots(recipe)
    ])

@cache
def generate_all_recipes_for(name, furnace_capacity=14):
    recipe = get_recipes()[name]

    found = [recipe]
    for i in [recipe] + uptier(recipe, furnace_capacity, found) + sidetier(recipe, furnace_capacity, found):
        if i not in found:
            found.append(i)
            for j in downtier(i, furnace_capacity, found):
                if j not in found:
                    found.append(j)
    return found


def only_minimal(recipes):
    return [ r for r in recipes if not is_bloated(r) ]


def is_bloated(recipe):
    primary = is_slot_stackable('Primary', recipe) and is_temperature_balanced_without_slot('Primary 2', recipe)
    secondary = is_slot_stackable('Secondary', recipe) and is_temperature_balanced_without_slot('Secondary 2', recipe)
    both = (
        is_slot_stackable('Primary', recipe) and
        is_slot_stackable('Secondary', recipe) and
        is_recipe_balanced({ key: recipe[key] for key in recipe if key != 'primary2' and key != 'secondary2' })
    )
    return primary or secondary or both


def is_temperature_balanced_without_slot(slot, recipe):
    return is_recipe_balanced({ key: recipe[key] for key in recipe if key != slot })


def is_recipe_balanced(recipe):
    return get_balancing_temperature(recipe) == recipe['Temperature']['herb'].temperature


def is_slot_stackable(slot, recipe):
    return (
        slot in recipe and
        slot + ' 2' in recipe and
        recipe[slot]['herb'] == recipe[slot + ' 2']['herb']
    )


def get_dao_exp(elixir):
    ratio = {
        1: 0.6,
        2: 0.4,
        3: 0.2,
        4: 0.12,
        5: 0.08572,
        6: 0.014545,
    }

    return int(elixir.value * ratio[elixir.grade])


if __name__ == '__main__':
    name = sys.argv[1]
    furnace_capacity = int(sys.argv[2]) if len(sys.argv) > 2 else 14

    print_recipes(only_minimal(generate_all_recipes_for(name, furnace_capacity)))


from unittest import TestCase, skip
class TestRecipes(TestCase):
    def test_that_herbs_can_be_loaded_from_spreadsheet(self):
        herbs = get_herbs()
        self.assertEqual('Azuresky Flower', herbs[0].name)
        self.assertEqual('Mending', herbs[0].primary)
        self.assertEqual('Focusing', herbs[0].secondary)
        self.assertEqual('Heat', herbs[0].temperature)
        self.assertEqual(1, herbs[0].grade)

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
        self.assertEqual(10, len(found))

    def test_that_the_temperature_of_the_temperature_herb_can_be_calculated(self):
        recipes = get_recipes()
        self.assertEqual('Heat', get_balancing_temperature(recipes['Expert Healing Elixir']))
        self.assertEqual('Cold', get_balancing_temperature(recipes['Divine Heart Elixir']))
        self.assertEqual('Balanced', get_balancing_temperature(recipes['Azure Heart Elixir']))

    def test_that_recipes_can_be_downtiered(self):
        recipes = get_recipes()
        self.assertEqual(2, len(downtier(recipes['Qi Guidance Elixir'])))

    def test_that_recipes_can_be_sidetiered(self):
        recipes = get_recipes()
        self.assertEqual(11, len(sidetier(recipes['Qi Guidance Elixir'])))

    def test_that_recipes_can_be_uptiered(self):
        recipes = get_recipes()
        self.assertEqual(171, len(uptier(recipes['Vitality Orb Elixir'])))
        self.assertEqual(6, len(uptier(recipes['Pure Heart Soul Tempering Elixir'])))

    def test_that_all_recipes_can_be_generated_for_name(self):
        self.assertEqual(112, len(generate_all_recipes_for('Pure Heart Soul Tempering Elixir')))
        self.assertEqual(4736, len(generate_all_recipes_for('Bloodrend Elixir')))

    def test_that_recipes_can_be_sorted(self):
        swordsage_recipes = generate_all_recipes_for('Swordsage Elixir')
        head, *tail = sort_recipes(swordsage_recipes, reverse=False)
        self.assertEqual(1, calculate_herb_types(head))

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

        recipe = get_recipes()['Qi Guidance Elixir']
        self.assertFalse(find_duplicates(downtier(recipe)))
        self.assertFalse(find_duplicates(sidetier(recipe)))
        self.assertFalse(find_duplicates(uptier(recipe)))
        self.assertFalse(find_duplicates(generate_all_recipes_for('Pure Heart Soul Tempering Elixir')))

    def test_that_elixirs_can_be_loaded_from_spreadsheet(self):
        self.assertEqual(126, len(get_elixirs()))
        self.assertEqual(143, get_elixir('Qi Guidance Elixir').value)
        print(get_elixir('Qi Guidance Elixir'))

    def test_that_recipe_can_be_converted_to_dict(self):
        recipes = get_recipes()
        self.assertEqual('Qi Guidance Elixir', recipe_to_dict(recipes['Qi Guidance Elixir'])['name'])
        self.assertEqual(143, recipe_to_dict(recipes['Qi Guidance Elixir'])['value'])

    def test_that_non_minimal_recipes_can_be_detected(self):
        recipes = sort_recipes(generate_all_recipes_for('Vitality Shard Elixir'), reverse=False)
        self.assertFalse(is_bloated(recipes[0]))
        self.assertTrue(is_bloated(recipes[1]))

    @skip
    def test_that_herb_images_can_be_loaded_from_spreadsheet(self):
        extract_images_to_static_dir()


def extract_images_to_static_dir():
    import openpyxl
    from openpyxl_image_loader import SheetImageLoader

    sheet = openpyxl.load_workbook(alchemy_guide)['Herbs']
    image_loader = SheetImageLoader(sheet)

    for i in range(2,153):
        name_cell = 'B' + str(i)
        img_cell = 'J' + str(i)

        herb_name = sheet[name_cell].value

        if image_loader.image_in(img_cell):
            image_loader.get(img_cell).save('static/images/{}.png'.format(herb_name))
