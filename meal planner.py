import json
import os
import random
from collections import Counter, defaultdict

# ----- Configurable data -----
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
SLOTS = ["Breakfast", "Lunch", "Dinner", "Snack"]
CATEGORY_KEYWORDS = {
    "protein": ["chicken", "egg", "eggs", "paneer", "tofu", "fish", "salmon", "tuna", "lentil", "dal", "beans", "chickpea", "turkey", "mutton"],
    "carb": ["rice", "bread", "roti", "noodles", "pasta", "oats", "chapati", "potato", "idli", "dosa"],
    "vegetable": ["spinach", "carrot", "tomato", "onion", "potato", "broccoli", "capsicum", "peas", "cucumber", "cabbage"],
    "fruit": ["apple", "banana", "orange", "berries", "mango", "grapes"],
    "dairy": ["milk", "yogurt", "curd", "cheese", "butter"],
    "healthy_fat": ["olive oil", "oil", "ghee", "nuts", "peanut", "almond", "walnut", "seeds"],
    "condiment": ["salt", "pepper", "spice", "turmeric", "garam masala", "soy sauce"],
    "beverage": ["tea", "coffee"],
}
CATEGORY_FALLBACKS = {
    "protein": ["eggs", "chicken", "tofu", "paneer"],
    "carb": ["rice", "bread", "oats"],
    "vegetable": ["spinach", "tomato", "carrot"],
    "fruit": ["banana", "apple"],
    "dairy": ["milk", "yogurt"],
    "healthy_fat": ["nuts", "olive oil"],
}
# Desired macro emphasis by goal - relative weights (protein, carb, veg)
GOAL_PROFILES = {
    "weight_loss": {"protein": 0.35, "carb": 0.30, "vegetable": 0.25, "dairy": 0.05, "healthy_fat": 0.05},
    "muscle_gain": {"protein": 0.40, "carb": 0.35, "vegetable": 0.15, "dairy": 0.05, "healthy_fat": 0.05},
    "balanced_diet": {"protein": 0.30, "carb": 0.35, "vegetable": 0.25, "dairy": 0.05, "healthy_fat": 0.05},
}
def save_json(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def load_json(filename, fallback=None):
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    return fallback

def normalize_item(s):
    return s.strip().lower()

def categorize_ingredient(item):
    item_l = item.lower()
    for cat, keys in CATEGORY_KEYWORDS.items():
        for k in keys:
            if k in item_l:
                return cat
    # try simple heuristics
    if any(x in item_l for x in ["milk", "yogurt", "cheese", "paneer"]):
        return "dairy"
    if any(x in item_l for x in ["oil", "ghee", "nuts", "almond", "walnut", "seeds"]):
        return "healthy_fat"
    return "other"

# ----- Core logic -----
def collect_user_info():
    print("User Profile Setup")
    name = input("Name: ").strip()
    while not name:
        print("Please enter a name.")
        name = input("Name: ").strip()

    def ask_int(prompt, default=None):
        while True:
            v = input(f"{prompt}{' ['+str(default)+']' if default else ''}: ").strip()
            if not v and default is not None:
                return default
            try:
                return int(v)
            except:
                print("Please enter a valid integer.")

    age = ask_int("Age", default=25)
    height_cm = ask_int("Height (cm)", default=170)

    print("Goals: 1) weight_loss  2) muscle_gain  3) balanced_diet")
    gmap = {"1": "weight_loss", "2": "muscle_gain", "3": "balanced_diet"}
    goal_choice = input("Choose goal (1/2/3) [3]: ").strip() or "3"
    goal = gmap.get(goal_choice, "balanced_diet")

    profile = {
        "name": name,
        "age": age,
        "height_cm": height_cm,
        "goal": goal,
    }
    print(f"Saved profile for {name} (goal: {goal})\n")
    return profile

def collect_pantry():
    print("Pantry Input")
    print("Enter a comma-separated list of ingredients you currently have (e.g. rice, eggs, spinach, milk).")
    raw = input("Pantry items: ").strip()
    if not raw:
        print("No items entered — planner will still try to generate meals but will suggest many items.")
        return []
    items = [normalize_item(x) for x in raw.split(",") if x.strip()]
    # dedupe preserving order
    seen = set()
    unique = []
    for it in items:
        if it not in seen:
            seen.add(it)
            unique.append(it)
    print(f"Registered {len(unique)} pantry items.\n")
    return unique

def build_category_map(pantry):
    cat_map = defaultdict(list)
    for it in pantry:
        cat = categorize_ingredient(it)
        cat_map[cat].append(it)
    return cat_map

def pick_ingredients_for_meal(cat_map, allow_other=True, prefer_categories=None, picks=2):
    """
    Randomly pick 'picks' ingredients from pantry using category preference.
    prefer_categories: list of categories to prefer (higher priority)
    """
    prefer_categories = prefer_categories or []
    chosen = set()

    # first try prefer categories
    for cat in prefer_categories:
        candidates = list(cat_map.get(cat, []))
        random.shuffle(candidates)
        while candidates and len(chosen) < picks:
            chosen.add(candidates.pop())

    # fill remaining from pantry across categories
    all_items = [it for cat, items in cat_map.items() for it in items]
    random.shuffle(all_items)
    for it in all_items:
        if len(chosen) >= picks:
            break
        chosen.add(it)

    if allow_other and len(chosen) < picks:
        # add generic staples if still short
        staples = ["bread", "rice", "oats", "milk", "egg", "banana"]
        for s in staples:
            if len(chosen) >= picks:
                break
            chosen.add(s)

    return list(chosen)

def generate_week_plan(pantry, profile):
    cat_map = build_category_map(pantry)
    goal = profile.get("goal", "balanced_diet")
    goal_profile = GOAL_PROFILES.get(goal, GOAL_PROFILES["balanced_diet"])

    week = {day: {} for day in DAYS}

    # create small pool of variety seeds: shuffle pantry to avoid same combos
    random.seed()  # system random
    for day in DAYS:
        for slot in SLOTS:
            # decide picks per slot: snack smaller (1-2), others 2-4
            if slot == "Snack":
                picks = random.choice([1, 2])
            else:
                picks = random.choice([2, 3])

            # choose prefer categories based on slot and goal
            if slot == "Breakfast":
                prefer = ["carb", "protein"] if goal != "weight_loss" else ["protein", "carb"]
            elif slot == "Lunch":
                prefer = ["protein", "vegetable"] if goal == "muscle_gain" else ["carb", "vegetable"]
            elif slot == "Dinner":
                prefer = ["protein", "vegetable"] if goal != "weight_loss" else ["vegetable", "protein"]
            else:  # Snack
                prefer = ["fruit", "dairy", "healthy_fat"]

            ingredients = pick_ingredients_for_meal(cat_map, picks=picks, prefer_categories=prefer)
            # small randomized name generation for the meal
            meal_name = create_meal_name(slot, ingredients)
            week[day][slot] = {"name": meal_name, "ingredients": ingredients}
    return week

def create_meal_name(slot, ingredients):
    # make a friendly meal name using 1-2 main ingredients
    main = ", ".join(ingredients[:2]) if ingredients else "Simple Meal"
    return f"{slot}: {main}"

def suggest_cart(pantry, week_plan, profile, top_n=8):
    """
    Suggest items for next shopping:
     - Look at categories that are underrepresented for the user's goal
     - Recommend useful items not present in pantry
    """
    cat_map = build_category_map(pantry)
    present_cats = {cat: len(items) for cat, items in cat_map.items()}
    goal = profile.get("goal", "balanced_diet")
    desired = GOAL_PROFILES.get(goal, GOAL_PROFILES["balanced_diet"])

    # Score categories by (desired weight - present fraction)
    total_present = sum(present_cats.values()) or 1
    scores = {}
    for cat, weight in desired.items():
        present_frac = present_cats.get(cat, 0) / total_present
        scores[cat] = weight - present_frac

    # Sort categories by need descending
    need_order = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    suggestions = []
    # For each needed category, propose fallback items not in pantry
    pantry_set = set(pantry)
    for cat, score in need_order:
        if score <= 0 and len(suggestions) >= top_n:
            break
        fallbacks = CATEGORY_FALLBACKS.get(cat, [])
        for f in fallbacks:
            if f not in pantry_set and f not in suggestions:
                suggestions.append(f)
                if len(suggestions) >= top_n:
                    break
        if len(suggestions) >= top_n:
            break
    # If still not enough suggestions, add general staples
    defaults = ["rice", "bread", "eggs", "milk", "spinach", "nuts", "oats"]
    for d in defaults:
        if d not in pantry_set and d not in suggestions:
            suggestions.append(d)
        if len(suggestions) >= top_n:
            break

    # Produce suggested quantities (naive)
    cart = [{"item": s, "qty": 1} for s in suggestions]
    return cart

def pretty_print_week(week):
    print("\n 7-Day Meal Plan")
    for day in DAYS:
        print(f"\n-- {day} --")
        for slot in SLOTS:
            meal = week[day].get(slot)
            if meal:
                ingr = ", ".join(meal["ingredients"]) if meal["ingredients"] else "—"
                print(f"  {slot:9}: {meal['name']} | Ingredients: {ingr}")
            else:
                print(f"  {slot:9}: —")

def main():
    print("Adaptive Meal Planner\n")
    profile = collect_user_info()
    save_json("user.json", profile)
    pantry = collect_pantry()
    week_plan = generate_week_plan(pantry, profile)
    save_json("meals.json", week_plan)
    cart = suggest_cart(pantry, week_plan, profile)
    save_json("cart.json", cart)
    print("\nFiles saved: user.json, meals.json, cart.json")
    pretty_print_week(week_plan)

    print("\nSuggested Shopping")
    if cart:
        for it in cart:
            print(f" - {it['item']}  x{it['qty']}")
    else:
        print("No suggestions — your pantry looks balanced for the goals you set.")

    print("\nThank you — meal plan and suggestions saved locally.")

if __name__ == "__main__":
    main()