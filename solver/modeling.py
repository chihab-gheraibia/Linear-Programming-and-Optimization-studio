"""Guided word-problem modeling for LP Studio.

No NLP and no AI are used here: the user describes the data in a small table
and this module turns that table into the usual course-style model, then runs
the existing engine and writes a template-based interpretation.
"""

from copy import deepcopy
from dataclasses import dataclass, field
import re

from .complementary import check_optimality
from .dual import dual_solution, dual_solution_to_dict
from .graphical import graphical_to_dict, solve_graphical
from .model import F, LP, fmt
from .sensitivity import sensitivity_report
from .simplex import solve


MODELING_EXAMPLES = {
    "athlete": {
        "id": "athlete",
        "title": "Régime de l'athlète",
        "lang": "fr",
        "type": "diet",
        "currency": "dh",
        "statement": (
            "Un athlète suit un régime et souhaite consommer la plus faible ration "
            "quotidienne de trois éléments nutritifs : protéines, vitamines et calcium. "
            "Les exigences quotidiennes sont de 16g de protéines, 12g de vitamines et "
            "18g de calcium. L'athlète achète deux types d'aliments P et Q : une unité "
            "de P comprend 2g de protéines, 1g de vitamines et 1g de calcium et coûte "
            "20 dh ; une unité de Q comprend 1g de protéines, 1g de vitamines et 3g de "
            "calcium et coûte 40 dh. L'athlète cherche la combinaison la moins coûteuse "
            "des quantités de P et Q qui respectera l'exigence de consommation minimale "
            "d'éléments nutritifs."
        ),
        "items": [
            {"name": "P", "unit": "unité", "price": "20"},
            {"name": "Q", "unit": "unité", "price": "40"},
        ],
        "resources": [
            {"name": "protéines", "unit": "g", "amount": "16", "op": ">=",
             "content": {"P": "2", "Q": "1"}},
            {"name": "vitamines", "unit": "g", "amount": "12", "op": ">=",
             "content": {"P": "1", "Q": "1"}},
            {"name": "calcium", "unit": "g", "amount": "18", "op": ">=",
             "content": {"P": "1", "Q": "3"}},
        ],
    },
    "furniture": {
        "id": "furniture",
        "title": "Atelier de mobilier",
        "lang": "fr",
        "type": "production",
        "currency": "Dh",
        "statement": (
            "Un atelier fabrique deux articles M1 et M2. Chaque article passe par trois "
            "ateliers : Menuiserie, Assemblage et Vernissage. Les disponibilités sont de "
            "20 heures de Menuiserie, 22 heures d'Assemblage et 12 heures de Vernissage. "
            "M1 consomme 1, 2 et 1 heures et rapporte 300 Dh ; M2 consomme 2, 1 et 1 "
            "heures et rapporte 200 Dh. On cherche la production maximisant le profit."
        ),
        "items": [
            {"name": "M1", "unit": "unité", "price": "300"},
            {"name": "M2", "unit": "unité", "price": "200"},
        ],
        "resources": [
            {"name": "Menuiserie", "unit": "heures", "amount": "20", "op": "<=",
             "content": {"M1": "1", "M2": "2"}},
            {"name": "Assemblage", "unit": "heures", "amount": "22", "op": "<=",
             "content": {"M1": "2", "M2": "1"}},
            {"name": "Vernissage", "unit": "heures", "amount": "12", "op": "<=",
             "content": {"M1": "1", "M2": "1"}},
        ],
    },
}


MODEL_TEMPLATES = {
    "fr": {
        "default_title": "Problème de programmation linéaire",
        "item_unit": "unité",
        "resource_unit": "unité",
        "step_variables": "Définition des variables de décision",
        "step_objective": "Fonction objectif",
        "step_constraints": "Contraintes",
        "step_nonneg": "Non-négativité",
        "step_complete": "Modèle mathématique complet",
        "decision_diet": "Soit {name} la quantité d'aliment {name} achetée (en {unit}).",
        "decision_production": "Soit {name} la quantité produite de {name} (en {unit}).",
        "objective_diet": "Minimiser le coût total : Z = {objective} (en {currency})",
        "objective_production": "Maximiser le profit total : Z = {objective} (en {currency})",
        "constraint_diet": "{name} : {lhs} {symbol} {rhs} ({phrase} {rhs} {unit} de {name} par jour)",
        "constraint_production": "{name} : {lhs} {symbol} {rhs} ({phrase} {rhs} {unit} de {name} disponibles)",
        "op_>=": "au moins",
        "op_<=": "au plus",
        "op_=": "exactement",
        "nonneg": "Les quantités sont non négatives : {names} ≥ 0.",
        "complete": "{lp_text}",
        "alias_note": "Le nom « {name} » n'est pas un identifiant ; il est noté {alias} dans le modèle.",
        "error_no_spec": "Envoyez un objet JSON décrivant le problème.",
        "error_lang": "La langue doit être 'fr' ou 'en'.",
        "error_type": "Le type doit être 'diet' ou 'production'.",
        "error_items_list": "La liste des aliments ou articles est manquante.",
        "error_resources_list": "La liste des ressources ou exigences est manquante.",
        "error_no_items": "Ajoutez au moins un aliment ou un article.",
        "error_no_resources": "Ajoutez au moins une ressource ou une exigence.",
        "error_empty_name": "Le nom d'un aliment, d'un article ou d'une ressource ne peut pas être vide.",
        "error_duplicate_name": "Deux éléments ne peuvent pas avoir le même nom : « {name} ».",
        "error_missing_number": "Il manque le nombre {label}.",
        "error_bad_number": "Le nombre {label} est invalide : « {value} ».",
        "error_negative": "Le nombre {label} ne peut pas être négatif.",
        "error_operator": "L'opérateur de « {name} » doit être <=, >= ou =.",
        "error_zero_row": "La ligne « {name} » ne contient aucun coefficient non nul.",
    },
    "en": {
        "default_title": "Linear programming problem",
        "item_unit": "unit",
        "resource_unit": "unit",
        "step_variables": "Decision variables",
        "step_objective": "Objective function",
        "step_constraints": "Constraints",
        "step_nonneg": "Non-negativity",
        "step_complete": "Complete mathematical model",
        "decision_diet": "Let {name} be the quantity of food {name} bought (in {unit}).",
        "decision_production": "Let {name} be the quantity produced of {name} (in {unit}).",
        "objective_diet": "Minimise total cost: Z = {objective} (in {currency})",
        "objective_production": "Maximise total profit: Z = {objective} (in {currency})",
        "constraint_diet": "{name}: {lhs} {symbol} {rhs} ({phrase} {rhs} {unit} of {name} per day)",
        "constraint_production": "{name}: {lhs} {symbol} {rhs} ({phrase} {rhs} {unit} of {name} available)",
        "op_>=": "at least",
        "op_<=": "at most",
        "op_=": "exactly",
        "nonneg": "Quantities are non-negative: {names} ≥ 0.",
        "complete": "{lp_text}",
        "alias_note": "The name '{name}' is not an identifier; it is written {alias} in the model.",
        "error_no_spec": "Send a JSON object describing the problem.",
        "error_lang": "The language must be 'fr' or 'en'.",
        "error_type": "The type must be 'diet' or 'production'.",
        "error_items_list": "The list of foods or products is missing.",
        "error_resources_list": "The list of resources or requirements is missing.",
        "error_no_items": "Add at least one food or one product.",
        "error_no_resources": "Add at least one resource or one requirement.",
        "error_empty_name": "The name of a food, product or resource cannot be empty.",
        "error_duplicate_name": "Two entries cannot have the same name: '{name}'.",
        "error_missing_number": "The number {label} is missing.",
        "error_bad_number": "The number {label} is invalid: '{value}'.",
        "error_negative": "The number {label} cannot be negative.",
        "error_operator": "The operator of '{name}' must be <=, >= or =.",
        "error_zero_row": "Row '{name}' has no non-zero coefficient.",
    },
}


INTERPRETATION_TEMPLATES = {
    "fr": {
        "section_decision": "Décision optimale",
        "section_resources": "Ressources / exigences",
        "section_shadow": "Prix fictifs (shadow prices)",
        "section_sensitivity": "Stabilité du plan (sensibilité)",
        "section_verification": "Vérification",
        "section_recommendations": "Recommandations / conclusion",
        "decision_diet": "Il faut acheter {quantities}, pour un coût minimal de {z} {currency}.",
        "decision_production": "Il faut produire {quantities}, pour un gain maximal de {z} {currency}.",
        "quantity": "{value} {unit} de {name}",
        "binding_diet": "{name} : saturée — exactement {value} {unit} exigés.",
        "nonbinding_diet": "{name} : non saturée — {value} {unit} pour une exigence de {rhs} {unit}, soit un excédent de {slack} {unit}.",
        "binding_production": "{name} : saturée — exactement {value} {unit} utilisés.",
        "nonbinding_production": "{name} : non saturée — {value} {unit} utilisés pour {rhs} {unit} disponibles, soit {slack} {unit} inutilisés.",
        "shadow_diet": "Chaque {unit} de {name} exigé en plus (ou en moins) fait varier le coût de {price} {currency}, tant que l'exigence reste dans [{low} ; {high}].",
        "shadow_production": "Chaque {unit} de {name} supplémentaire fait gagner {price} {currency}, tant que la disponibilité reste dans [{low} ; {high}].",
        "zero_shadow_diet": "Prix fictif nul : modifier légèrement cette exigence ne change pas le coût (valable jusqu'à {high} {unit}).",
        "zero_shadow_production": "Prix fictif nul : modifier légèrement cette ressource ne change pas le gain (valable jusqu'à {high} {unit}).",
        "no_upper": "sans borne supérieure",
        "no_lower": "sans borne inférieure",
        "sensitivity_cost": "Le plan reste optimal tant que le prix de {name} est dans [{low} ; {high}] {currency}.",
        "sensitivity_profit": "Le plan reste optimal tant que le gain de {name} est dans [{low} ; {high}] {currency}.",
        "verification_diet": "Dualité forte : coût primal = valeur duale = {z}. Complémentarité : {check}.",
        "verification_production": "Dualité forte : profit primal = valeur duale = {z}. Complémentarité : {check}.",
        "check_ok": "vérifiée",
        "check_pending": "non vérifiée ({status})",
        "recommend_drivers": "Ce sont {names} qui pilotent la solution.",
        "recommend_none": "Aucune contrainte ne pilote le résultat actuel.",
        "recommend_redundant": "{names} n'est pas saturée et n'influe donc pas sur la solution actuelle.",
        "recommend_sensitive": "Le paramètre le plus sensible est {name} : sa marge relative est la plus faible.",
        "status_infeasible": "Aucune combinaison ne satisfait toutes les exigences : le problème est irréalisable.",
        "status_unbounded": "Le résultat peut être amélioré sans limite : le problème est non borné.",
        "status_alternative": "Plusieurs plans optimaux existent ; celui-ci est l'un d'eux.",
        "status_degenerate": "La solution est dégénérée : les prix fictifs peuvent ne pas être uniques.",
        "status_unknown": "Le modèle n'a pas encore de solution optimale exploitable.",
        "unavailable": "Non disponible tant que le modèle n'a pas de solution optimale.",
    },
    "en": {
        "section_decision": "Optimal decision",
        "section_resources": "Resources / requirements",
        "section_shadow": "Shadow prices",
        "section_sensitivity": "Stability of the plan (sensitivity)",
        "section_verification": "Verification",
        "section_recommendations": "Recommendations / conclusion",
        "decision_diet": "Buy {quantities}, for a minimum cost of {z} {currency}.",
        "decision_production": "Produce {quantities}, for a maximum profit of {z} {currency}.",
        "quantity": "{value} {unit} of {name}",
        "binding_diet": "{name}: binding — exactly {value} {unit} required.",
        "nonbinding_diet": "{name}: not binding — {value} {unit} for a requirement of {rhs} {unit}, a surplus of {slack} {unit}.",
        "binding_production": "{name}: binding — exactly {value} {unit} used.",
        "nonbinding_production": "{name}: not binding — {value} {unit} used out of {rhs} {unit}, leaving {slack} {unit} unused.",
        "shadow_diet": "Each extra (or missing) {unit} of {name} changes the cost by {price} {currency}, while the requirement stays in [{low} ; {high}].",
        "shadow_production": "Each extra {unit} of {name} adds {price} {currency}, while the availability stays in [{low} ; {high}].",
        "zero_shadow_diet": "Zero shadow price: a small change in this requirement does not change the cost (valid up to {high} {unit}).",
        "zero_shadow_production": "Zero shadow price: a small change in this resource does not change the profit (valid up to {high} {unit}).",
        "no_upper": "no upper bound",
        "no_lower": "no lower bound",
        "sensitivity_cost": "The plan stays optimal while the price of {name} is in [{low} ; {high}] {currency}.",
        "sensitivity_profit": "The plan stays optimal while the profit of {name} is in [{low} ; {high}] {currency}.",
        "verification_diet": "Strong duality: primal cost = dual value = {z}. Complementary slackness: {check}.",
        "verification_production": "Strong duality: primal profit = dual value = {z}. Complementary slackness: {check}.",
        "check_ok": "verified",
        "check_pending": "not verified ({status})",
        "recommend_drivers": "{names} drive the solution.",
        "recommend_none": "No constraint currently drives the result.",
        "recommend_redundant": "{names} is not binding and does not affect the current solution.",
        "recommend_sensitive": "The most sensitive parameter is {name}: it has the smallest relative margin.",
        "status_infeasible": "No combination satisfies every requirement: the problem is infeasible.",
        "status_unbounded": "The result can be improved without limit: the problem is unbounded.",
        "status_alternative": "Several optimal plans exist; this one is among them.",
        "status_degenerate": "The solution is degenerate: shadow prices may not be unique.",
        "status_unknown": "The model has no usable optimal solution yet.",
        "unavailable": "Unavailable until the model has an optimal solution.",
    },
}


SECTION_KEYS = (
    "decision", "resources", "shadow", "sensitivity", "verification",
    "recommendations",
)

NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
NUMBER_TOKEN_RE = re.compile(
    r"(?<![\d.,/])(?P<number>\d+\s*/\s*\d+|\d*[.,]\d+|\d+)"
    r"(?P<unit>\s*[A-Za-zÀ-ÿµ%]+)?(?![\d.,/])"
)


class ModelingError(ValueError):
    """A friendly validation error with one message per supported language."""

    def __init__(self, messages, lang="fr"):
        """Store both messages so the API can answer in the requested language."""
        self.messages = dict(messages)
        self.lang = lang if lang in ("fr", "en") else "fr"
        super().__init__(self.messages[self.lang])

    @property
    def message(self):
        """Return the message in the language chosen for this request."""
        return self.messages[self.lang]


@dataclass
class ModelingResult:
    """The LP object plus the five course-style modeling steps."""

    spec: dict
    lp: LP
    lp_text: str
    steps: list
    variables: list
    rows: list
    notes: list = field(default_factory=list)

    def to_dict(self):
        """Return a JSON-ready preview for the live modeling panel."""
        return {
            "ok": True,
            "title": self.spec["title"],
            "lang": self.spec["lang"],
            "type": self.spec["type"],
            "lp_text": self.lp_text,
            "lp": self.lp.to_dict(),
            "steps": self.steps,
            "variables": self.variables,
            "notes": self.notes,
        }


@dataclass
class AnalysisReport:
    """Everything the Modeling Lab needs for one guided problem."""

    model: ModelingResult
    status: str
    simplex: object
    graphical: object
    dual: object
    sensitivity: object
    complementary: object
    interpretation: dict

    def to_dict(self):
        """Return a JSON-ready bundle for the analyze endpoint and the UI."""
        payload = self.simplex.to_dict()
        payload.update({
            "ok": True,
            "lang": self.model.spec["lang"],
            "status": self.status,
            "modeling": self.model.to_dict(),
            "lp_text": self.model.lp_text,
            "model": self.model.lp.to_dict(),
            "graphical": self.graphical,
            "dual": self.dual,
            "sensitivity": self.sensitivity,
            "complementary": self.complementary,
            "interpretation": self.interpretation,
            "z_display": number_text(self.simplex.z, self.model.spec["lang"]),
            "x_display": None if self.simplex.x is None else [
                number_text(value, self.model.spec["lang"]) for value in self.simplex.x
            ],
        })
        return payload


def list_modeling_examples():
    """Return full modeling specs, safe for the browser to modify."""
    return [deepcopy(item) for item in MODELING_EXAMPLES.values()]


def get_modeling_example(key):
    """Return one deep-copied modeling spec by its stable id."""
    item = MODELING_EXAMPLES.get(key)
    return deepcopy(item) if item is not None else None


def error(messages, lang):
    """Raise a ModelingError using the templates of one language."""
    raise ModelingError(messages, lang)


def template(lang, key, **values):
    """Read one MODEL_TEMPLATES entry and fill its placeholders."""
    return MODEL_TEMPLATES[lang][key].format(**values)


def normalize_spec(spec):
    """Check the wizard payload and fill in defaults with friendly errors."""
    if not isinstance(spec, dict):
        error({code: MODEL_TEMPLATES[code]["error_no_spec"] for code in MODEL_TEMPLATES}, "fr")
    lang = spec.get("lang", "fr")
    if lang not in ("fr", "en"):
        error({"fr": MODEL_TEMPLATES["fr"]["error_lang"],
               "en": MODEL_TEMPLATES["en"]["error_lang"]}, lang)
    kind = spec.get("type", "diet")
    if kind not in ("diet", "production"):
        error({code: MODEL_TEMPLATES[code]["error_type"] for code in MODEL_TEMPLATES}, lang)
    items, resources = spec.get("items"), spec.get("resources")
    if not isinstance(items, list):
        error({code: MODEL_TEMPLATES[code]["error_items_list"] for code in MODEL_TEMPLATES}, lang)
    if not isinstance(resources, list):
        error({code: MODEL_TEMPLATES[code]["error_resources_list"] for code in MODEL_TEMPLATES}, lang)
    if not items:
        error({code: MODEL_TEMPLATES[code]["error_no_items"] for code in MODEL_TEMPLATES}, lang)
    if not resources:
        error({code: MODEL_TEMPLATES[code]["error_no_resources"] for code in MODEL_TEMPLATES}, lang)
    return {
        "lang": lang,
        "type": kind,
        "title": str(spec.get("title") or "").strip() or MODEL_TEMPLATES[lang]["default_title"],
        "statement": str(spec.get("statement") or ""),
        "currency": str(spec.get("currency") or "").strip() or "dh",
        "items": items,
        "resources": resources,
    }


def parse_decimal(value, label, lang):
    """Parse one wizard number: 3,5 / 3.5 / 1/2 all become exact Fractions."""
    if value is None or not str(value).strip():
        messages = {code: MODEL_TEMPLATES[code]["error_missing_number"].format(label=label)
                    for code in MODEL_TEMPLATES}
        error(messages, lang)
    text = str(value).strip().replace("\u00a0", "").replace(" ", "").replace(",", ".")
    text = text.replace("−", "-")
    try:
        return F(text)
    except (ValueError, ZeroDivisionError):
        messages = {code: MODEL_TEMPLATES[code]["error_bad_number"].format(
            label=label, value=value) for code in MODEL_TEMPLATES}
        error(messages, lang)


def positive_number(value, label, lang):
    """Parse a non-negative number or raise a friendly bilingual error."""
    amount = parse_decimal(value, label, lang)
    if amount < 0:
        messages = {code: MODEL_TEMPLATES[code]["error_negative"].format(label=label)
                    for code in MODEL_TEMPLATES}
        error(messages, lang)
    return amount


def clean_name(value, lang):
    """Trim a name and reject empty names in both languages."""
    name = str(value or "").strip()
    if not name:
        error({code: MODEL_TEMPLATES[code]["error_empty_name"] for code in MODEL_TEMPLATES}, lang)
    return name


def check_duplicates(names, lang):
    """Reject two identical names, ignoring case and surrounding spaces."""
    seen = set()
    for name in names:
        key = name.casefold()
        if key in seen:
            messages = {code: MODEL_TEMPLATES[code]["error_duplicate_name"].format(name=name)
                        for code in MODEL_TEMPLATES}
            error(messages, lang)
        seen.add(key)


def safe_symbol(name, index):
    """Return a parser-safe variable name; display names stay in the text."""
    return name if NAME_RE.fullmatch(name) else f"x{index + 1}"


def localized_unit(unit, lang):
    """Translate only the two default unit words when the report language changes."""
    translations = {"unité": "unit", "unites": "unit", "unités": "unit",
                    "heures": "hours", "hour": "hours"}
    if lang == "en":
        return translations.get(str(unit).strip().casefold(), unit)
    return {"unit": "unité", "hours": "heures"}.get(str(unit).strip().casefold(), unit)


def normalize_items(items, lang):
    """Return validated item names, units, prices and safe LP symbols."""
    rows = [item if isinstance(item, dict) else {} for item in items]
    names = [clean_name(item.get("name"), lang) for item in rows]
    check_duplicates(names, lang)
    default_unit = MODEL_TEMPLATES[lang]["item_unit"]
    variables = []
    for index, (item, name) in enumerate(zip(rows, names)):
        price = positive_number(item.get("price"), name, lang)
        variables.append({
            "name": name, "alias": f"x{index + 1}",
            "display_symbol": safe_symbol(name, index),
            "unit": localized_unit(item.get("unit") or default_unit, lang),
            "price": price,
        })
    return variables


def normalize_resources(resources, variables, lang, kind):
    """Return validated resource rows with one exact coefficient per item."""
    source = [row if isinstance(row, dict) else {} for row in resources]
    names = [clean_name(row.get("name"), lang) for row in source]
    check_duplicates(names, lang)
    default_op = ">=" if kind == "diet" else "<="
    rows = []
    for name, row in zip(names, source):
        op = str(row.get("op") or default_op)
        if op not in ("<=", ">=", "="):
            messages = {code: MODEL_TEMPLATES[code]["error_operator"].format(name=name)
                        for code in MODEL_TEMPLATES}
            error(messages, lang)
        amount = positive_number(row.get("amount"), name, lang)
        content = row.get("content") if isinstance(row.get("content"), dict) else {}
        coeffs = [positive_number(content.get(var["name"], 0), f"{name}/{var['name']}", lang)
                  for var in variables]
        if not any(coeffs):
            messages = {code: MODEL_TEMPLATES[code]["error_zero_row"].format(name=name)
                        for code in MODEL_TEMPLATES}
            error(messages, lang)
        unit = localized_unit(row.get("unit") or
                              MODEL_TEMPLATES[lang]["resource_unit"], lang)
        rows.append({"name": name, "unit": unit, "op": op,
                     "amount": amount, "coeffs": coeffs})
    return rows


def lhs_text(coefficients, names, hide_one=False):
    """Write a sum with display names, e.g. '2P + 1Q' or '2x1 + x2'."""
    parts = []
    for value, name in zip(coefficients, names):
        if value == 0:
            continue
        sign = "-" if value < 0 else ("+" if parts else "")
        number = "" if hide_one and abs(value) == 1 else fmt(abs(value))
        parts.append(f"{sign} {number}{name}".strip())
    return " ".join(parts) or "0"


def objective_text(coefficients, names):
    """Write the objective with spaced coefficients, e.g. '20 P + 40 Q'."""
    return " + ".join(f"{fmt(value)} {name}" for value, name in zip(coefficients, names))


def make_steps(data, variables, rows, lp, lp_text):
    """Build the five corrigé-style modeling sections in the chosen language."""
    lang, kind = data["lang"], data["type"]
    names = [var["name"] for var in variables]
    decisions = "\n".join(
        template(lang, f"decision_{kind}", name=var["name"], unit=var["unit"])
        for var in variables
    )
    aliases = "\n".join(
        template(lang, "alias_note", name=var["name"], alias=var["alias"])
        for var in variables if var["display_symbol"] != var["name"]
    )
    if aliases:
        decisions += "\n" + aliases
    constraints = "\n".join(
        template(lang, f"constraint_{kind}", name=row["name"],
                 lhs=lhs_text(row["coeffs"], names),
                 symbol={"<=": "≤", ">=": "≥", "=": "="}[row["op"]],
                 rhs=fmt(row["amount"]), unit=row["unit"],
                 phrase=template(lang, "op_" + row["op"]))
        for row in rows
    )
    objective = template(lang, f"objective_{kind}",
                         objective=objective_text(lp.c, names), currency=data["currency"])
    nonneg = template(lang, "nonneg", names=", ".join(names))
    complete = template(lang, "complete", lp_text=lp_text)
    titles = ["step_variables", "step_objective", "step_constraints",
              "step_nonneg", "step_complete"]
    return [{"number": index + 1, "title": MODEL_TEMPLATES[lang][key], "text": text}
            for index, (key, text) in enumerate(zip(
                titles, [decisions, objective, constraints, nonneg, complete]))]


def build_model(spec):
    """Turn a guided wizard spec into an LP plus the five modeling steps."""
    data = normalize_spec(spec)
    variables = normalize_items(data["items"], data["lang"])
    rows = normalize_resources(data["resources"], variables, data["lang"], data["type"])
    coefficients = [var["price"] for var in variables]
    matrix = [row["coeffs"] for row in rows]
    operators = [row["op"] for row in rows]
    rhs = [row["amount"] for row in rows]
    aliases = [var["alias"] for var in variables]
    lp = LP.build("min" if data["type"] == "diet" else "max",
                  coefficients, matrix, operators, rhs, aliases)
    lp_text = lp.to_text()
    steps = make_steps(data, variables, rows, lp, lp_text)
    notes = [template(data["lang"], "alias_note", name=var["name"], alias=var["alias"])
             for var in variables if var["display_symbol"] != var["name"]]
    return ModelingResult(data, lp, lp_text, steps, variables, rows, notes)


def to_exact_number(text):
    """Convert a highlighter token to a Fraction, or None when it is not a number."""
    try:
        return parse_decimal(text, "token", "fr")
    except ModelingError:
        return None


def numbers_in_text(text):
    """Find numbers and their units in a pasted statement, with exact positions."""
    found = []
    for match in NUMBER_TOKEN_RE.finditer(str(text or "")):
        raw_number = match.group("number")
        value = to_exact_number(raw_number)
        if value is None:
            continue
        raw = match.group(0)
        found.append({
            "start": match.start("number"),
            "end": match.end(),
            "value": fmt(value),
            "raw": raw,
            "unit": (match.group("unit") or "").strip(),
        })
    return found


def number_text(value, lang="fr"):
    """Write an exact value with at most two decimals and an exact fraction."""
    if value is None:
        return "—"
    exact = F(value)
    if exact.denominator == 1:
        return str(exact.numerator)
    decimal = f"{round(float(exact), 2):.2f}".rstrip("0").rstrip(".")
    if lang == "fr":
        decimal = decimal.replace(".", ",")
    if exact.denominator <= 100 and abs(exact.numerator) <= 10000:
        return f"{decimal} ({fmt(exact)})"
    return decimal


def unit_label(unit, value, lang):
    """Pluralise the two standard unit words used by the wizard."""
    if F(value) == 1:
        return unit
    if lang == "fr" and unit == "unité":
        return "unités"
    if lang == "en" and unit == "unit":
        return "units"
    return unit


def interval_text(row, lang, tpl):
    """Write a sensitivity interval, including open ends."""
    low = number_text(row["lower"], lang) if row["lower"] is not None else tpl["no_lower"]
    high = number_text(row["upper"], lang) if row["upper"] is not None else tpl["no_upper"]
    return low, high


def left_value(coefficients, values):
    """Compute a constraint left-hand side without any float arithmetic."""
    return sum((coefficient * F(value) for coefficient, value in zip(coefficients, values)), F(0))


def usage(row, x):
    """Return the used amount, the surplus/shortfall and whether the row is tight."""
    used = left_value(row["coeffs"], x)
    if row["op"] == "<=":
        difference = row["amount"] - used
    elif row["op"] == ">=":
        difference = used - row["amount"]
    else:
        difference = F(0)
    return used, difference, difference == 0


def interpretation_tpl(lang):
    """Return the interpretation dictionary of one language."""
    return INTERPRETATION_TEMPLATES[lang]


def decision_section(model, simplex, tpl):
    """Write the optimal quantities and objective in the vocabulary of the problem."""
    lang, kind = model.spec["lang"], model.spec["type"]
    if simplex.status != "optimal" or simplex.x is None:
        return tpl["status_" + simplex.status if simplex.status in
                   ("infeasible", "unbounded") else "status_unknown"]
    quantities = ", ".join(
        tpl["quantity"].format(value=number_text(value, lang),
                               unit=unit_label(var["unit"], value, lang),
                               name=var["name"])
        for value, var in zip(simplex.x, model.variables)
    )
    text = tpl[f"decision_{kind}"].format(
        quantities=quantities, z=number_text(simplex.z, lang),
        currency=model.spec["currency"])
    if simplex.multiple_optima:
        text += " " + tpl["status_alternative"]
    if simplex.degenerate:
        text += " " + tpl["status_degenerate"]
    return text


def resources_section(model, simplex, tpl):
    """Say which rows are saturated and compute every slack with exact values."""
    lang = model.spec["lang"]
    if simplex.status != "optimal" or simplex.x is None:
        return tpl["unavailable"]
    lines = []
    for item in model.rows:
        used, difference, binding = usage(item, simplex.x)
        key = "binding" if binding else "nonbinding"
        lines.append(tpl[f"{key}_{model.spec['type']}"].format(
            name=item["name"], unit=item["unit"],
            value=number_text(used, lang), rhs=number_text(item["amount"], lang),
            slack=number_text(difference, lang)))
    return "\n".join(lines)


def shadow_section(model, simplex, dual, sensitivity, tpl):
    """Explain every shadow price using its exact validity interval."""
    lang, kind = model.spec["lang"], model.spec["type"]
    if not dual or not sensitivity or simplex.status != "optimal":
        return tpl["unavailable"]
    lines = []
    for index, row in enumerate(model.rows):
        item = sensitivity["rhs"][index]
        price = F(dual["shadow_prices"][index])
        low, high = interval_text(item, lang, tpl)
        if price == 0:
            lines.append(tpl[f"zero_shadow_{kind}"].format(
                name=row["name"], unit=row["unit"], high=high))
        else:
            lines.append(tpl[f"shadow_{kind}"].format(
                name=row["name"], unit=row["unit"],
                price=number_text(price, lang),
                currency=model.spec["currency"], low=low, high=high))
    if simplex.degenerate or len(dual.get("alternative_ys", [])) > 1:
        lines.append(tpl["status_degenerate"])
    return "\n".join(lines)


def sensitivity_section(model, sensitivity, tpl):
    """Write the optimality interval of each cost or profit in words."""
    lang, kind = model.spec["lang"], model.spec["type"]
    if not sensitivity:
        return tpl["unavailable"]
    key = "sensitivity_cost" if kind == "diet" else "sensitivity_profit"
    lines = []
    for var, row in zip(model.variables, sensitivity["objective"]):
        low, high = interval_text(row, lang, tpl)
        lines.append(tpl[key].format(name=var["name"], low=low, high=high,
                                     currency=model.spec["currency"]))
    return "\n".join(lines)


def verification_section(model, simplex, dual, complementary, tpl):
    """Report strong duality and the complementary-slackness verdict."""
    lang, kind = model.spec["lang"], model.spec["type"]
    if not dual or simplex.status != "optimal":
        return tpl["unavailable"]
    check = tpl["check_ok"] if complementary and complementary["verdict"] == "optimal" \
        else tpl["check_pending"].format(status=complementary["verdict"] if complementary else "?")
    return tpl[f"verification_{kind}"].format(
        z=number_text(simplex.z, lang), check=check)


def relative_margin(row):
    """Return the smallest relative distance from the current cost to its bounds."""
    current = abs(F(row["current"])) or F(1)
    margins = []
    if row["lower"] is not None:
        margins.append(abs(F(row["current"]) - F(row["lower"])) / current)
    if row["upper"] is not None:
        margins.append(abs(F(row["upper"]) - F(row["current"])) / current)
    return min(margins) if margins else None


def recommendations_section(model, simplex, dual, sensitivity, tpl):
    """Generate two or three short teaching conclusions from the computed data."""
    if simplex.status != "optimal" or not sensitivity:
        return tpl["status_" + simplex.status if simplex.status in
                   ("infeasible", "unbounded") else "status_unknown"]
    rows = model.rows
    binding = [row["name"] for index, row in enumerate(rows)
               if usage(row, simplex.x)[2] and dual and
               F(dual["shadow_prices"][index]) != 0]
    lines = [tpl["recommend_drivers"].format(names=", ".join(binding)) if binding
             else tpl["recommend_none"]]
    loose = [row["name"] for row in rows if not usage(row, simplex.x)[2]]
    if loose:
        lines.append(tpl["recommend_redundant"].format(names=", ".join(loose)))
    margins = [(relative_margin(row), var["name"])
               for row, var in zip(sensitivity["objective"], model.variables)]
    margins = [item for item in margins if item[0] is not None]
    if margins:
        lines.append(tpl["recommend_sensitive"].format(name=min(margins)[1]))
    return "\n".join(lines)


def make_interpretation(model, simplex, dual, sensitivity, complementary):
    """Build the six readable interpretation sections in the chosen language."""
    tpl = interpretation_tpl(model.spec["lang"])
    builders = (
        ("decision", lambda: decision_section(model, simplex, tpl)),
        ("resources", lambda: resources_section(model, simplex, tpl)),
        ("shadow", lambda: shadow_section(model, simplex, dual, sensitivity, tpl)),
        ("sensitivity", lambda: sensitivity_section(model, sensitivity, tpl)),
        ("verification", lambda: verification_section(model, simplex, dual, complementary, tpl)),
        ("recommendations", lambda: recommendations_section(
            model, simplex, dual, sensitivity, tpl)),
    )
    sections = {
        key: {"title": tpl["section_" + key], "text": build()}
        for key, build in builders
    }
    plain = "\n\n".join(f"{item['title']}\n{item['text']}" for item in sections.values())
    return {"lang": model.spec["lang"], "status": simplex.status,
            "sections": sections, "plain_text": plain}


def analyze(spec):
    """Run modeling, simplex, graph, dual, sensitivity and interpretation."""
    model = build_model(spec)
    simplex = solve(model.lp)
    graphical = None
    if model.lp.n == 2:
        graph = solve_graphical(model.lp)
        graphical = graphical_to_dict(graph, model.lp)
    dual, sensitivity, complementary = None, None, None
    if simplex.status == "optimal":
        dual = dual_solution(model.lp, simplex)
        dual = dual_solution_to_payload(dual, simplex, model.spec["lang"])
        sensitivity = sensitivity_report(model.lp, simplex)
        complementary = check_optimality(model.lp, simplex.x).to_dict()
    interpretation = make_interpretation(
        model, simplex, dual, sensitivity, complementary)
    return AnalysisReport(model, simplex.status, simplex, graphical,
                          dual, sensitivity, complementary, interpretation)


def dual_solution_to_payload(info, simplex, lang):
    """Expose the dual in the same shape as the existing /api/dual route."""
    payload = dual_solution_to_dict(info)
    payload["strong_duality"] = (
        simplex.status == "optimal" and info["w"] is not None and info["w"] == simplex.z)
    payload["z_primal"] = None if simplex.z is None else fmt(simplex.z)
    payload["z_display"] = number_text(simplex.z, lang)
    return payload
