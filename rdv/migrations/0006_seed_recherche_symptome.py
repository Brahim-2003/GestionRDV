from django.db import migrations


# Contenu confirmé en session de cadrage : catégories larges regroupant des
# symptômes précis, chacun mappé vers une ou plusieurs spécialités parmi les
# 10 codes existants de Medecin.SPECIALITES. La catégorie n'est pas stockée
# (RechercheSymptome n'a pas ce champ) ; elle sert uniquement à organiser
# cette liste ci-dessous pour la future interface hybride (catégories ->
# symptômes cochables), qui devra recréer ce regroupement côté code.
SYMPTOMES_SEED = [
    # Fièvre
    ("Fièvre persistante / grippe", ["generaliste"]),
    ("Frissons et douleurs musculaires", ["generaliste"]),
    # Douleur
    ("Douleur thoracique", ["cardiologue", "generaliste"]),
    ("Mal de dos", ["orthopediste", "generaliste"]),
    ("Douleur articulaire", ["orthopediste", "generaliste"]),
    ("Migraine / mal de tête récurrent", ["neurologue", "generaliste"]),
    ("Douleur abdominale", ["generaliste"]),
    # Peau
    ("Éruption cutanée / démangeaisons", ["dermatologue"]),
    ("Grain de beauté suspect", ["dermatologue"]),
    ("Acné", ["dermatologue"]),
    # Digestion
    ("Brûlures d'estomac", ["generaliste"]),
    ("Nausées / vomissements", ["generaliste"]),
    ("Diarrhée / constipation", ["generaliste"]),
    # Respiration / ORL
    ("Toux persistante", ["generaliste"]),
    ("Essoufflement", ["cardiologue", "generaliste"]),
    ("Mal de gorge / oreille", ["orl"]),
    # Yeux
    ("Baisse de vision", ["ophtalmologue"]),
    ("Douleur oculaire", ["ophtalmologue"]),
    # Bien-être mental
    ("Anxiété / stress", ["psychiatre", "generaliste"]),
    ("Troubles du sommeil", ["psychiatre", "generaliste"]),
    ("Tristesse persistante", ["psychiatre", "generaliste"]),
    # Santé féminine
    ("Douleurs de règles", ["gynecologue"]),
    ("Suivi de grossesse", ["gynecologue"]),
    # Enfant
    ("Fièvre ou symptôme chez l'enfant", ["pediatre", "generaliste"]),
    # Autre
    ("Je ne sais pas", ["generaliste"]),
]


def seed_recherche_symptome(apps, schema_editor):
    RechercheSymptome = apps.get_model('rdv', 'RechercheSymptome')
    for symptome, specialites in SYMPTOMES_SEED:
        RechercheSymptome.objects.get_or_create(
            symptome=symptome,
            defaults={'specialites_suggerees': specialites},
        )


def unseed_recherche_symptome(apps, schema_editor):
    RechercheSymptome = apps.get_model('rdv', 'RechercheSymptome')
    noms = [symptome for symptome, _ in SYMPTOMES_SEED]
    RechercheSymptome.objects.filter(symptome__in=noms).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('rdv', '0005_listeattentecreneau'),
    ]

    operations = [
        migrations.RunPython(seed_recherche_symptome, unseed_recherche_symptome),
    ]
