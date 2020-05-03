from django.shortcuts import render
from django_tables2 import SingleTableMixin
from django_filters.views import FilterView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.contrib.auth.models import Group

from kicoma.users.models import User

from .models import Item, Recipe, Allergen, MealType, TargetGroup, Unit, VAT, \
    Article, Ingredient, StockIssue, StockReceipt, DailyMenu
from .tables import RecipeTable, RecipeFilter, StockReceiptTable, StockReceiptFilter
from .forms import RecipeSearchForm, StockReceiptSearchForm

# import logging
# Get an instance of a logger
# logger = logging.getLogger(__name__)


def index(request):
    allergenCount = Allergen.objects.all().count()
    mealTypeCount = MealType.objects.all().count()
    targetGroupCount = TargetGroup.objects.all().count()
    unitCount = Unit.objects.all().count()
    vatCount = VAT.objects.all().count()

    recipeCount = Recipe.objects.all().count()
    ingredientCount = Ingredient.objects.all().count()
    articleCount = Article.objects.all().count()
    stockIssueCount = StockIssue.objects.all().count()
    stockReceiptCount = StockReceipt.objects.all().count()
    itemCount = Item.objects.all().count()
    dailyMenuCount = DailyMenu.objects.all().count()

    userCount = User.objects.all().count()
    groupCount = Group.objects.all().count()

    return render(request, 'kitchen/home.html', {
        'allergenCount': allergenCount,
        'mealTypeCount': mealTypeCount,
        'targetGroupCount': targetGroupCount,
        'unitCount': unitCount,
        'vatCount': vatCount,

        'recipeCount': recipeCount,
        'ingredientCount': ingredientCount,
        'articleCount': articleCount,
        'stockIssueCount': stockIssueCount,
        'stockReceiptCount': stockReceiptCount,
        'itemCount': itemCount,
        'dailyMenuCount': dailyMenuCount,

        "groupCount": groupCount,
        "userCount": userCount
    })


def about(request):
    return render(request, 'kitchen/about.html')


class RecipeListView(SingleTableMixin, LoginRequiredMixin, FilterView):
    model = Recipe
    table_class = RecipeTable
    template_name = 'kitchen/recipe/show.html'
    filterset_class = RecipeFilter
    form_class = RecipeSearchForm
    paginate_by = 12


class RecipeCreateView(SuccessMessageMixin, LoginRequiredMixin, CreateView):
    model = Recipe
    fields = "__all__"
    template_name = 'kitchen/recipe/create.html'
    success_message = "Recept %(name)s byl vytvořen"

    def get_success_url(self):
        return reverse_lazy('kitchen:showRecipies')


class RecipeUpdateView(SuccessMessageMixin, LoginRequiredMixin, UpdateView):
    model = Recipe
    fields = "__all__"
    template_name = 'kitchen/recipe/edit.html'
    success_message = "Recept %(name)s byl aktualizován"

    def get_success_url(self):
        return reverse_lazy('kitchen:showRecipies')


class RecipeDeleteView(SuccessMessageMixin, LoginRequiredMixin, DeleteView):
    model = Recipe
    fields = "__all__"
    form_class = RecipeSearchForm
    template_name = 'kitchen/recipe/delete.html'
    success_message = "Recept %(name)s byl odstraněn"

    def get_success_url(self):
        return reverse_lazy('kitchen:showRecipies')


# StockReceipt

class StockReceiptListView(SingleTableMixin, LoginRequiredMixin, FilterView):
    model = StockReceipt
    table_class = StockReceiptTable
    template_name = 'kitchen/stockreceipt/list.html'
    filterset_class = StockReceiptFilter
    form_class = StockReceiptSearchForm
    paginate_by = 12


class StockReceiptCreateView(SuccessMessageMixin, LoginRequiredMixin, CreateView):
    model = Item
    fields = ["amount", "unit", "priceWithoutVat", "vat"]
    template_name = 'kitchen/stockreceipt/create.html'
    success_message = "Příjemka %(name)s byla vytvořena a zásoby zboží na skladu aktualizovány"

    def get_success_url(self):
        return reverse_lazy('kitchen:showStockReceipts')
