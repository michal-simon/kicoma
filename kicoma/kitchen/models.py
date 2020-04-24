from django.db import models
from django.urls import reverse
from django.core.validators import MaxValueValidator, MinValueValidator


class VAT(models.Model):

    class Meta:
        verbose_name_plural = "DPH"

    percentage = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        unique=True, verbose_name="Výše", help_text="DPH procenta")
    name = models.CharField(max_length=100, unique=True, verbose_name="Sazba", help_text="DPH sazba")

    def __str__(self):
        return str(self.percentage) + '% - ' + self.name


class Allergen(models.Model):

    class Meta:
        verbose_name_plural = "Alergény"

    code = models.CharField(max_length=10, unique=True, verbose_name="Kód", help_text="Kód alergénu")
    description = models.CharField(max_length=100, unique=True, verbose_name="Název", help_text="Název alergénu")

    def __str__(self):
        return self.code + ' - ' + self.description


class StockUnit(models.Model):

    class Meta:
        verbose_name_plural = "Jednotky"

    name = models.CharField(max_length=2, unique=True, verbose_name="Jednotka",
                            help_text="Objemová nebo váhová jednotka zboží")

    def __str__(self):
        return self.name


class TargetGroup(models.Model):

    class Meta:
        verbose_name_plural = "Skupiny strávníků"

    name = models.CharField(max_length=100, unique=True, verbose_name="Skupina strávníka",
                            help_text="Skupina pro kterou se připravuje jídlo")

    def __str__(self):
        return self.name


class MealType(models.Model):

    class Meta:
        verbose_name_plural = "Druhy jídla"

    name = models.CharField(max_length=30, unique=True, verbose_name="Druh jídla",
                            help_text="Druh jídla v rámci dne")
    category = models.CharField(max_length=30, verbose_name="Kategorie", help_text="Kategorie druhu jídla")

    def __str__(self):
        return self.name


class StockItem(models.Model):

    class Meta:
        verbose_name_plural = "Skladové položky"

    name = models.CharField(max_length=100, verbose_name="Skladová položka")
    criticalAmount = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(1000)],
        unique=True, verbose_name="Kritické množství", help_text="Minimální množství na skladu")
    averagePrice = models.DecimalField(
        max_digits=6, decimal_places=2, verbose_name="Průměrná cena")
    normPrice = models.DecimalField(
        max_digits=9, decimal_places=5, blank=True, null=True, verbose_name="Cena normy")
    comment = models.CharField(max_length=200, verbose_name="Poznámka")
    coefficient = models.DecimalField(
        max_digits=5, decimal_places=4, default=1,
        verbose_name="Koeficient", help_text="Koeficient  propočtu do receptu")
    unit = models.ForeignKey(StockUnit, on_delete=models.CASCADE, verbose_name="Jednotka")
    allergen = models.ManyToManyField(Allergen, blank=True, verbose_name="Alergény")

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        """Returns the url to access a particular instance of the model."""
        return reverse('model-detail-view', args=[str(self.id)])

    def display_allergens(self):
        """Create a string for the Allergens. This is required to display allergen in Admin and user table view."""
        return ', '.join(allergen.code for allergen in self.allergen.all())

    display_allergens.short_description = 'Alergény'


class RecipeIngredient(models.Model):

    class Meta:
        verbose_name_plural = "Suroviny v receptu"

    amount = models.DecimalField(
        decimal_places=4, max_digits=6,
        unique=True, verbose_name="Množství", help_text="Množství suroviny")
    stockItem = models.ForeignKey(StockItem, on_delete=models.CASCADE, verbose_name="Skladová položka",
                                  help_text="Skladová položka")

    def __str__(self):
        return self.stockItem.name + '-  ' + str(self.amount) + 'x'


class Recipe(models.Model):

    class Meta:
        verbose_name_plural = "Recepty"

    name = models.CharField(max_length=100, unique=True, verbose_name="Jméno")
    norm_amount = models.PositiveSmallIntegerField(verbose_name="Normovaný počet", help_text="Počet porcí")
    comment = models.CharField(max_length=200, verbose_name="Poznámka")
    recipeIngredient = models.ForeignKey(RecipeIngredient, on_delete=models.CASCADE, verbose_name="Seznam surovin",
                                         help_text="Suroviny v receptu")

    def __str__(self):
        return self.name


class DailyMenu(models.Model):

    class Meta:
        verbose_name_plural = "Denní jídlo"

    date = models.DateField(verbose_name="Datum")
    amount = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(1000)],
        unique=True, verbose_name="Počet", help_text="Počet porcí")
    targetGroup = models.ForeignKey(TargetGroup, on_delete=models.CASCADE, verbose_name="Skupina strávníka",
                                    help_text="Skupina pro kterou se připravuje jídlo")
    mealType = models.ForeignKey(MealType, on_delete=models.CASCADE, verbose_name="Druh jídla",
                                 help_text="Druh jídla v rámci dne")
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE, verbose_name="Recept",
                               help_text="Vybraný recept")

    def __str__(self):
        return str(self.date) + ' - ' + self.mealType.name + ' - ' + str(self.amount) + 'x - ' + self.targetGroup.name


# class Recipe(models.Model):

#     class Meta:
#         verbose_name_plural = "Recept"
#         # ordering = ['code']

#     recipeBook = models.ForeignKey(RecipeBook, on_delete=models.CASCADE)
#     ingredient = models.ForeignKey(StockItem, on_delete=models.CASCADE)
#     amount = models.PositiveSmallIntegerField(verbose_name="Množství")
#     unit = models.ForeignKey(StockUnit, on_delete=models.CASCADE, verbose_name="Jednotka")

#     def __str__(self):
#         return self.recipeBook.name + " - " + self.ingredient.name
