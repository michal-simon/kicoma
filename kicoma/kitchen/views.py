import logging
import io
from datetime import datetime
from contextlib import redirect_stdout

from django.core import management
from django.core.files.storage import FileSystemStorage

from django.urls import reverse_lazy
from django.utils.safestring import mark_safe
from django.http import HttpResponseRedirect, HttpResponse
from django.contrib import messages
from django.shortcuts import render, get_object_or_404
from django.core.exceptions import ValidationError

from django.db import transaction, connection
from django.db.models import F, Count

from django.views.generic import DetailView
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from django.views.generic.list import ListView
from django.views.generic.base import TemplateView, View

from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.contrib.auth.models import Group, ContentType, Permission

from wkhtmltopdf.views import PDFTemplateView
from django_tables2 import SingleTableMixin
from django_filters.views import FilterView

from tablib import Dataset

from kicoma.users.models import User

from .models import StockIssueArticle, StockReceiptArticle, Recipe, Allergen, MealType, MealGroup, VAT, \
    Article, HistoricalArticle, RecipeArticle, StockIssue, StockReceipt, DailyMenu, DailyMenuRecipe

from .tables import StockReceiptTable, StockReceiptArticleTable, StockReceiptFilter
from .tables import StockIssueTable, StockIssueArticleTable, StockIssueFilter
from .tables import ArticleTable, ArticleFilter
from .tables import DailyMenuTable, DailyMenuFilter
from .tables import DailyMenuRecipeTable
from .tables import RecipeTable, RecipeFilter, RecipeArticleTable

from .forms import RecipeForm, RecipeArticleForm, RecipeSearchForm
from .forms import StockReceiptForm, StockReceiptSearchForm, StockReceiptArticleForm
from .forms import StockIssueForm, StockIssueSearchForm, StockIssueArticleForm, StockIssueFromDailyMenuForm
from .forms import ArticleForm, ArticleSearchForm
from .forms import DailyMenuSearchForm, DailyMenuPrintForm, DailyMenuForm, DailyMenuRecipeForm
from .forms import FoodConsumptionPrintForm

from .functions import convertUnits

from .admin import ArticleResource

# Get an instance of a logger
logger = logging.getLogger(__name__)


def about(request):
    allergenCount = Allergen.objects.all().count()
    meal_typeCount = MealType.objects.all().count()
    mealGroupCount = MealGroup.objects.all().count()
    vatCount = VAT.objects.all().count()

    recipeCount = Recipe.objects.all().count()
    recipe_article_count = RecipeArticle.objects.all().count()
    article_count = Article.objects.all().count()
    article_allergen_count = Article.objects.all().aggregate(count=Count('allergen'))['count']
    historical_article_count = HistoricalArticle.objects.all().count()
    stockIssueCount = StockIssue.objects.all().count()
    stockReceiptCount = StockReceipt.objects.all().count()
    stock_issue_article_count = StockIssueArticle.objects.all().count()
    stock_receipt_article_count = StockReceiptArticle.objects.all().count()
    dailyMenuCount = DailyMenu.objects.all().count()
    dailyMenuRecipeCount = DailyMenuRecipe.objects.all().count()

    userCount = User.objects.all().count()
    groupCount = Group.objects.all().count()

    # service tables content
    content_type_count = ContentType.objects.all().count()
    permission_count = Permission.objects.all().count()
    with connection.cursor() as cursor:
        cursor.execute('select count(*) from django_migrations')
        row = cursor.fetchone()
        migration_count = row[0]

    with connection.cursor() as cursor:
        cursor.execute('select count(*) from django_session')
        row = cursor.fetchone()
        session_count = row[0]

    with connection.cursor() as cursor:
        cursor.execute('select count(*) from django_site')
        row = cursor.fetchone()
        site_count = row[0]

    with connection.cursor() as cursor:
        cursor.execute('select count(*) from users_user_groups')
        row = cursor.fetchone()
        user_group_rel_count = row[0]

    total_records = allergenCount + meal_typeCount + mealGroupCount + \
        vatCount + recipeCount + recipe_article_count + article_count + article_allergen_count + \
        historical_article_count + stockIssueCount + stockReceiptCount + stock_issue_article_count + \
        stock_receipt_article_count + dailyMenuCount + dailyMenuRecipeCount + userCount + groupCount + \
        content_type_count + permission_count + migration_count + session_count + site_count + user_group_rel_count

    logger.info("processing index")

    return render(request, 'kitchen/about.html', {
        'allergenCount': allergenCount,
        'meal_typeCount': meal_typeCount,
        'mealGroupCount': mealGroupCount,
        'vatCount': vatCount,

        'recipeCount': recipeCount,
        'recipe_article_count': recipe_article_count,
        'article_count': article_count,
        'article_allergen_count': article_allergen_count,
        'historical_article_count': historical_article_count,
        'stockIssueCount': stockIssueCount,
        'stockReceiptCount': stockReceiptCount,
        'stock_issue_article_count': stock_issue_article_count,
        'stock_receipt_article_count': stock_receipt_article_count,
        'dailyMenuCount': dailyMenuCount,
        'dailyMenuRecipeCount': dailyMenuRecipeCount,

        "groupCount": groupCount,
        "userCount": userCount,

        "content_type_count": content_type_count,
        'permission_count': permission_count,
        "migration_count": migration_count,
        "session_count": session_count,
        'site_count': site_count,
        'user_group_rel_count': user_group_rel_count,

        'total_records': total_records
    })


def changelog(request):
    return render(request, 'kitchen/changelog.html')


def docs(request):
    return render(request, 'kitchen/docs.html')


def exportData(request):
    file_name = 'data.json'
    with open(file_name, "w") as f:
        management.call_command('dumpdata', 'kitchen', exclude=['contenttypes', 'auth'], stdout=f)
        f.close()
        response = HttpResponse(open(file_name, "rb"), content_type="application/json")
        response['Content-Disposition'] = 'attachment; filename='+file_name
        messages.success(request, "Všechna data byla exportována")
        return response


class ImportDataView(TemplateView):
    template_name = 'kitchen/import.html'

    def post(self, request, **kwargs):
        context = {}
        if len(request.FILES) == 0:
            messages.error(
                self.request,
                "Není vybrán vstupní soubor, použij tlačítko Browse a vyber soubor.")
            return super(ImportDataView, self).render_to_response(context)
        uploaded_file = request.FILES['myfile']
        fs = FileSystemStorage()
        filename = fs.save(uploaded_file.name, uploaded_file)
        f = io.StringIO()
        try:
            with redirect_stdout(f):
                management.call_command('flush', interactive=False, verbosity=1)
                management.call_command('loaddata', "./kicoma/kitchen/fixtures/skupiny.json", verbosity=1)
                management.call_command('loaddata', "./kicoma/kitchen/fixtures/uzivatele.json", verbosity=1)
                management.call_command('loaddata', fs.path(filename), verbosity=1)
                messages.success(self.request, "Data úspěšně nahrána: "+f.getvalue())
        except Exception as e:
            messages.success(self.request, "Chyba při výmazu dat před importem: "+e)
        return super(ImportDataView, self).render_to_response(context)


class ArticleListView(SingleTableMixin, LoginRequiredMixin, FilterView):
    model = Article
    table_class = ArticleTable
    template_name = 'kitchen/article/list.html'
    filterset_class = ArticleFilter
    form_class = ArticleSearchForm
    paginate_by = 15

    def get_context_data(self, **kwargs):
        context = super(ArticleListView, self).get_context_data(**kwargs)
        context['total_stock_price'] = Article.sum_total_price()
        return context


class ArticleLackListView(SingleTableMixin, LoginRequiredMixin, FilterView):
    model = Article
    table_class = ArticleTable
    template_name = 'kitchen/article/listlack.html'
    filterset_class = ArticleFilter
    form_class = ArticleSearchForm
    paginate_by = 15

    def get_queryset(self):
        # show only articles where
        return super().get_queryset().filter(on_stock__lt=F('min_on_stock'))


class ArticleCreateView(SuccessMessageMixin, LoginRequiredMixin, CreateView):
    model = Article
    form_class = ArticleForm
    template_name = 'kitchen/article/create.html'
    success_message = "Zboží %(article)s bylo založeno, je možné zadávat příjemky"
    success_url = reverse_lazy('kitchen:showArticles')


class ArticleUpdateView(SuccessMessageMixin, LoginRequiredMixin, UpdateView):
    model = Article
    form_class = ArticleForm
    template_name = 'kitchen/article/update.html'
    success_message = "Zboží %(article)s bylo aktualizováno"
    success_url = reverse_lazy('kitchen:showArticles')


class ArticlePDFView(LoginRequiredMixin, PDFTemplateView):
    template_name = 'kitchen/article/pdf.html'
    filename = 'Seznam_zbozi.pdf'
    cmd_options = {
        'margin-top': 15,
        'margin-bottom': 15,
        'margin-left': 15,
        'margin-right': 15,
    }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['articles'] = Article.objects.all()
        context['title'] = "Seznam zboží na skladu"
        context['total_stock_price'] = Article.sum_total_price()
        return context


class ArticleExportView(LoginRequiredMixin, View):

    def get(self, *args, **kwargs):
        data = ArticleResource().export()
        response = HttpResponse(
            data.xlsx, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        response['Content-Disposition'] = 'attachment; filename=seznam-zbozi.xlsx'
        messages.success(self.request, "Seznam zboží byl exportován")
        return response


class ArticleImportView(TemplateView):
    template_name = 'kitchen/article/import.html'

    def post(self, request, **kwargs):
        article_resource = ArticleResource()
        dataset = Dataset()
        context = {}  # set your context
        if len(request.FILES) == 0:
            messages.error(
                self.request,
                "Není vybrán vstupní soubor, použij tlačítko Browse a vyber exportovaný a upravený MS Excel soubor.")
            return super(ArticleImportView, self).render_to_response(context)
        new_articles = request.FILES['myfile']
        imported_data = dataset.load(new_articles.read())
        result = article_resource.import_data(imported_data, dry_run=True,
                                              collect_failed_rows=True)  # Test the data import
        if result.has_errors() or result.has_validation_errors():
            messages.error(self.request, "Chyba v průběhu importu. Chybná data: {}".format(result.failed_dataset))
        else:
            article_resource.import_data(imported_data, dry_run=False)  # Actually import now
            messages.success(self.request, "Seznam zboží byl importován. Importováno {} řádků, z toho {} vloženo, \
                {} aktualizováno, {} vymazáno, {} přeskočeno, {} s chybou a {} neplatných řádků"
                             .format(result.total_rows, result.totals['new'], result.totals['update'],
                                     result.totals['delete'], result.totals['skip'], result.totals['error'],
                                     result.totals['invalid']))
        return super(ArticleImportView, self).render_to_response(context)


class ArticleHistoryDetailView(LoginRequiredMixin, DetailView):
    model = Article
    template_name = 'kitchen/article/listhistory.html'

    def get_context_data(self, **kwargs):
        context = super(ArticleHistoryDetailView, self).get_context_data(**kwargs)
        context['article_name'] = kwargs['object'].article
        context['table'] = kwargs['object'].history.all()
        return context


class StockTakePDFView(LoginRequiredMixin, PDFTemplateView):
    template_name = 'kitchen/stocktake/pdf.html'
    filename = 'Seznam_zbozi_na_skladu.pdf'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['articles'] = Article.objects.all()
        context['title'] = "Seznam zboží na skladu ke kontrole"
        return context


class RecipeListView(SingleTableMixin, LoginRequiredMixin, FilterView):
    model = Recipe
    table_class = RecipeTable
    template_name = 'kitchen/recipe/list.html'
    filterset_class = RecipeFilter
    form_class = RecipeSearchForm
    paginate_by = 15


class RecipeCreateView(SuccessMessageMixin, LoginRequiredMixin, CreateView):
    model = Recipe
    form_class = RecipeForm
    template_name = 'kitchen/recipe/create.html'
    success_message = "Recept %(recipe)s byl vytvořen, přidej ingredience"

    def get_success_url(self):
        return reverse_lazy('kitchen:showRecipeArticles', kwargs={'pk': self.object.id})


class RecipeUpdateView(SuccessMessageMixin, LoginRequiredMixin, UpdateView):
    model = Recipe
    form_class = RecipeForm
    template_name = 'kitchen/recipe/update.html'
    success_message = "Recept %(recipe)s byl aktualizován"
    success_url = reverse_lazy('kitchen:showRecipes')


class RecipeDeleteView(SuccessMessageMixin, LoginRequiredMixin, DeleteView):
    model = Recipe
    fields = "__all__"
    # form_class = RecipeSearchForm
    template_name = 'kitchen/recipe/delete.html'
    success_message = "Recept %(recipe)s byl odstraněn"
    success_url = reverse_lazy('kitchen:showRecipes')


class RecipeListPDFView(LoginRequiredMixin, PDFTemplateView):
    template_name = 'kitchen/recipe/pdf_list.html'
    filename = 'Seznam_receptu.pdf'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['recipes'] = Recipe.objects.all()
        context['recipes_total'] = Recipe.objects.all().count()
        context['title'] = "Seznam receptů"
        return context


class RecipePDFView(LoginRequiredMixin, PDFTemplateView):
    template_name = 'kitchen/recipe/pdf.html'
    filename = 'Recept.pdf'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        recipe = Recipe.objects.filter(pk=self.kwargs['pk']).get()
        context['recipe'] = recipe
        context['recipe_articles'] = RecipeArticle.objects.filter(recipe=recipe)
        context['title'] = recipe.recipe
        return context


class RecipeArticleListView(SingleTableMixin, LoginRequiredMixin, FilterView):
    model = RecipeArticle
    table_class = RecipeArticleTable
    template_name = 'kitchen/recipe/listarticles.html'
    paginate_by = 15

    def get_context_data(self, **kwargs):
        context = super(RecipeArticleListView, self).get_context_data(**kwargs)
        context['recipe'] = Recipe.objects.filter(pk=self.kwargs['pk'])[0]
        return context

    def get_queryset(self):
        # show only recipe ingedients
        return super().get_queryset().filter(recipe=self.kwargs["pk"])


class RecipeArticleCreateView(SuccessMessageMixin, LoginRequiredMixin, CreateView):
    model = RecipeArticle
    form_class = RecipeArticleForm
    template_name = 'kitchen/recipe/createarticle.html'
    success_message = "Zboží %(article)s bylo přidáno do receptu"

    def get_success_url(self):
        return reverse_lazy('kitchen:showRecipeArticles', kwargs={'pk': self.kwargs['pk']})

    def get_context_data(self, **kwargs):
        context = super(RecipeArticleCreateView, self).get_context_data(**kwargs)
        context['recipe'] = Recipe.objects.filter(pk=self.kwargs['pk']).get()
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        recipe = context['recipe']
        recipe_article = form.save(commit=False)
        try:
            convertUnits(recipe_article.amount,
                         recipe_article.unit, recipe_article.article.unit)
        except ValidationError as err:
            messages.warning(self.request, err.message)
            return super(RecipeArticleCreateView, self).form_invalid(form)
        recipe_article.recipe = Recipe.objects.filter(pk=recipe.id).get()
        recipe_article.save()
        return super(RecipeArticleCreateView, self).form_valid(form)


class RecipeArticleUpdateView(SuccessMessageMixin, LoginRequiredMixin, UpdateView):
    model = RecipeArticle
    form_class = RecipeArticleForm
    template_name = 'kitchen/recipe/updatearticle.html'
    success_message = "Zboží %(article)s bylo aktualizováno"

    def get_success_url(self):
        return reverse_lazy('kitchen:showRecipeArticles', kwargs={'pk': self.kwargs['pk']})

    def get_context_data(self, **kwargs):
        context = super(RecipeArticleUpdateView, self).get_context_data(**kwargs)
        context['recipe_article_before'] = RecipeArticle.objects.filter(pk=self.kwargs['pk']).get()
        return context

    def form_valid(self, form):
        recipe_article = form.save(commit=False)
        try:
            convertUnits(recipe_article.amount,
                         recipe_article.unit, recipe_article.article.unit)
        except ValidationError as err:
            messages.warning(self.request, err.message)
            return super(RecipeArticleUpdateView, self).form_invalid(form)
        recipe_article.recipe = RecipeArticle.objects.filter(pk=recipe_article.id)[0].recipe
        recipe_article.save()
        self.kwargs = {'pk': recipe_article.recipe.id}
        return super(RecipeArticleUpdateView, self).form_valid(form)


class RecipeArticleDeleteView(SuccessMessageMixin, LoginRequiredMixin, DeleteView):
    model = RecipeArticle
    template_name = 'kitchen/recipe/deletearticle.html'
    success_message = "Zboží bylo odstraněno"
    recipe_id = 0

    def get_success_url(self):
        return reverse_lazy('kitchen:showRecipeArticles', kwargs={'pk': self.recipe_id})

    def get_context_data(self, **kwargs):
        context = super(RecipeArticleDeleteView, self).get_context_data(**kwargs)
        context['recipe_article_before'] = RecipeArticle.objects.filter(pk=self.kwargs['pk']).get()
        return context

    def delete(self, request, *args, **kwargs):
        recipe_article = get_object_or_404(RecipeArticle, pk=self.kwargs['pk'])
        self.recipe_id = recipe_article.recipe.id
        return super(RecipeArticleDeleteView, self).delete(request, *args, **kwargs)


class DailyMenuListView(SingleTableMixin, LoginRequiredMixin, FilterView):
    model = DailyMenu
    table_class = DailyMenuTable
    template_name = 'kitchen/dailymenu/list.html'
    filterset_class = DailyMenuFilter
    form_class = DailyMenuSearchForm
    paginate_by = 15


class DailyMenuCreateView(SuccessMessageMixin, LoginRequiredMixin, CreateView):
    model = DailyMenu
    form_class = DailyMenuForm
    template_name = 'kitchen/dailymenu/create.html'
    success_message = "Denní menu pro den %(date)s bylo vytvořeno, přidej recepty"

    def get_success_url(self):
        return reverse_lazy('kitchen:showDailyMenuRecipes', kwargs={'pk': self.object.id})


class DailyMenuUpdateView(SuccessMessageMixin, LoginRequiredMixin, UpdateView):
    model = DailyMenu
    form_class = DailyMenuForm
    template_name = 'kitchen/dailymenu/update.html'
    success_message = "Denní menu pro den %(date)s bylo aktualizováno včetně výdejky ke schválení"
    success_url = reverse_lazy('kitchen:showDailyMenus')


class DailyMenuDeleteView(SuccessMessageMixin, LoginRequiredMixin, DeleteView):
    model = DailyMenu
    fields = "__all__"
    template_name = 'kitchen/dailymenu/delete.html'
    success_message = "Denní menu pro den %(date)s bylo odstraněno"
    success_url = reverse_lazy('kitchen:showDailyMenus')


class DailyMenuPDFView(LoginRequiredMixin, PDFTemplateView):
    template_name = 'kitchen/dailymenu/pdf.html'
    filename = 'Denni_menu.pdf'

    def get(self, request, *args, **kwargs):
        try:
            date = request.GET['date']
            datetime.strptime(date, "%d.%m.%Y")
        except ValueError as e:
            messages.warning(self.request, "Chybně zadané datum. Požadovaný formát je dd.mm.rr. Chyba: {}".format(e))
            return HttpResponseRedirect(reverse_lazy('kitchen:filterPrintDailyMenu'))
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        date = self.request.GET['date']
        meal_group = self.request.GET['meal_group']
        if len(meal_group) == 0:
            daily_menu_recipes = DailyMenuRecipe.objects.filter(daily_menu__date=datetime.strptime(date, "%d.%m.%Y"))
        else:
            daily_menu_recipes = DailyMenuRecipe.objects.filter(
                daily_menu__date=datetime.strptime(date, "%d.%m.%Y"), daily_menu__meal_group=meal_group)
            context['meal_group_filter'] = "Filtrováno pro skupinu strávníků: " + \
                MealGroup.objects.filter(pk=meal_group).get().meal_group
        context['title'] = "Denní menu pro " + date
        context['daily_menu_recipes'] = daily_menu_recipes
        return context


class DailyMenuPrintView(LoginRequiredMixin, CreateView):
    model = DailyMenu
    form_class = DailyMenuPrintForm
    template_name = 'kitchen/dailymenu/print.html'


class DailyMenuRecipeListView(SingleTableMixin, LoginRequiredMixin, FilterView):
    model = DailyMenuRecipe
    table_class = DailyMenuRecipeTable
    template_name = 'kitchen/dailymenu/listrecipe.html'
    paginate_by = 15

    def get_context_data(self, **kwargs):
        context = super(DailyMenuRecipeListView, self).get_context_data(**kwargs)
        context['dailymenu'] = DailyMenu.objects.filter(pk=self.kwargs['pk'])[0]
        return context

    def get_queryset(self):
        # show only DailyMeny recipes
        return super().get_queryset().filter(daily_menu=self.kwargs["pk"])


class DailyMenuRecipeCreateView(SuccessMessageMixin, LoginRequiredMixin, CreateView):
    model = DailyMenuRecipe
    form_class = DailyMenuRecipeForm
    template_name = 'kitchen/dailymenu/createrecipe.html'
    success_message = 'Recept %(recipe)s byl vytvořen'

    def get_success_url(self):
        return reverse_lazy('kitchen:showDailyMenuRecipes', kwargs={'pk': self.kwargs['pk']})

    def get_context_data(self, **kwargs):
        context = super(DailyMenuRecipeCreateView, self).get_context_data(**kwargs)
        context['daily_menu'] = DailyMenu.objects.filter(pk=self.kwargs['pk']).get()
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        daily_menu = context['daily_menu']
        daily_menu_recipe = form.save(commit=False)
        daily_menu_recipe.daily_menu = DailyMenu.objects.filter(pk=daily_menu.id)[0]
        daily_menu_recipe.save()
        return super(DailyMenuRecipeCreateView, self).form_valid(form)


class DailyMenuRecipeUpdateView(SuccessMessageMixin, LoginRequiredMixin, UpdateView):
    model = DailyMenuRecipe
    form_class = DailyMenuRecipeForm
    template_name = 'kitchen/dailymenu/updaterecipe.html'
    success_message = "Recept %(recipe)s byl aktualizován"

    def get_success_url(self):
        return reverse_lazy('kitchen:showDailyMenuRecipes', kwargs={'pk': self.kwargs['pk']})

    def get_context_data(self, **kwargs):
        context = super(DailyMenuRecipeUpdateView, self).get_context_data(**kwargs)
        context['dailymenurecipe_before'] = DailyMenuRecipe.objects.filter(pk=self.kwargs['pk'])[0]
        return context

    def form_valid(self, form):
        daily_menu_recipe = form.save(commit=False)
        daily_menu_recipe.daily_menu = DailyMenuRecipe.objects.filter(pk=daily_menu_recipe.id)[0].daily_menu
        daily_menu_recipe.save()
        self.kwargs = {'pk': daily_menu_recipe.daily_menu.id}
        return super(DailyMenuRecipeUpdateView, self).form_valid(form)


class DailyMenuRecipeDeleteView(SuccessMessageMixin, LoginRequiredMixin, DeleteView):
    model = DailyMenuRecipe
    template_name = 'kitchen/dailymenu/deleterecipe.html'
    success_message = "Recept byl odstraněn"
    daily_menu_id = 0

    def get_success_url(self):
        return reverse_lazy('kitchen:showDailyMenuRecipes', kwargs={'pk': self.daily_menu_id})

    def get_context_data(self, **kwargs):
        context = super(DailyMenuRecipeDeleteView, self).get_context_data(**kwargs)
        context['dailymenurecipe_before'] = DailyMenuRecipe.objects.filter(pk=self.kwargs['pk']).get()
        return context

    def delete(self, request, *args, **kwargs):
        recipe = get_object_or_404(DailyMenuRecipe, pk=self.kwargs['pk'])
        self.daily_menu_id = recipe.daily_menu.id
        return super(DailyMenuRecipeDeleteView, self).delete(request, *args, **kwargs)


class StockIssueListView(SingleTableMixin, LoginRequiredMixin, FilterView):
    model = StockIssue
    table_class = StockIssueTable
    template_name = 'kitchen/stockissue/list.html'
    filterset_class = StockIssueFilter
    form_class = StockIssueSearchForm
    paginate_by = 15


class StockIssueCreateView(SuccessMessageMixin, LoginRequiredMixin, CreateView):
    model = StockIssue
    form_class = StockIssueForm
    template_name = 'kitchen/stockissue/create.html'
    success_message = "Výdejka byla vytvořena a je možné přidávat zboží"

    def form_valid(self, form):
        form.instance.user_created = self.request.user
        self.object = form.save()
        return super(StockIssueCreateView, self).form_valid(form)

    def get_success_url(self):
        return reverse_lazy('kitchen:createStockIssueArticle', kwargs={'pk': self.object.id})


class StockIssueFromDailyMenuCreateView(SuccessMessageMixin, LoginRequiredMixin, CreateView):
    model = StockIssue
    form_class = StockIssueFromDailyMenuForm
    template_name = 'kitchen/stockissue/create_from_daily_menu.html'
    success_url = reverse_lazy('kitchen:showStockIssues')

    # do not save form which contains DailyMenu but save StockIssue on that date
    def form_valid(self, form):
        date = self.request.POST['date']
        daily_menus = DailyMenu.objects.filter(date=datetime.strptime(date, "%d.%m.%Y"))
        if len(daily_menus) < 1:
            form.add_error('date', "Pro zadané datum není vytvořeno denní menu")
            return super(StockIssueFromDailyMenuCreateView, self).form_invalid(form)
        count = StockIssue.createFromDailyMenu(daily_menus, date, self.request.user)
        messages.success(
            self.request, 'Výdejka pro den {} vytvořena a vyskladňuje {} druhů zboží'.format(date, count))
        return HttpResponseRedirect(self.success_url)


class StockIssueUpdateView(SuccessMessageMixin, LoginRequiredMixin, UpdateView):
    model = StockIssue
    form_class = StockIssueForm
    template_name = 'kitchen/stockissue/update.html'
    success_message = "Poznámka výdejky byla aktualizována"
    success_url = reverse_lazy('kitchen:showStockIssues')


class StockIssueRefreshView(LoginRequiredMixin, View):
    model = StockIssue

    def get(self, *args, **kwargs):
        stock_issue = StockIssue.objects.filter(pk=kwargs['pk']).get()
        if stock_issue.approved:
            messages.warning(self.request, "Aktualizace neprovedena - výdejka je již vyskladněna")
            return HttpResponseRedirect(reverse_lazy('kitchen:showStockIssues',))
        comment = stock_issue.comment
        if "Pro " not in comment:
            messages.warning(self.request, "Aktualizace zboží je možná jenom pro výdejku vytvořenou z denního menu")
        else:
            date = comment[4:]
            with transaction.atomic():
                stock_issue.delete()
                daily_menus = DailyMenu.objects.filter(date=datetime.strptime(date, "%d.%m.%Y"))
                if len(daily_menus) < 1:
                    messages.error('date', "Pro zadané datum není vytvořeno denní menu")
                    return HttpResponseRedirect(reverse_lazy('kitchen:showStockIssues'))
                count = StockIssue.createFromDailyMenu(daily_menus, date, self.request.user)
                messages.success(
                    self.request, "Seznam zboží na výdejce byl aktualizován dle aktuálních receptů na denním menu a vyskladňuje {} druhů zboží".format(count))
        return HttpResponseRedirect(reverse_lazy('kitchen:showStockIssues'))


class StockIssueDeleteView(SuccessMessageMixin, LoginRequiredMixin, DeleteView):
    model = StockIssue
    template_name = 'kitchen/stockissue/delete.html'
    success_message = "Výdejka ze dne %(created)s byla odstraněna"
    success_url = reverse_lazy('kitchen:showStockIssues')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        stock_issue = StockIssue.objects.filter(pk=self.kwargs['pk']).get()
        stock_issue_articles = StockIssueArticle.objects.filter(stock_issue_id=self.kwargs['pk'])
        context['stock_issue'] = stock_issue
        context['stock_issue_articles'] = stock_issue_articles
        context['total_price'] = stock_issue.total_price
        return context

    def post(self, request, *args, **kwargs):
        stock_issue = StockIssue.objects.filter(pk=self.kwargs['pk']).get()
        if stock_issue.approved:
            messages.warning(self.request, "Výmaz neproveden - výdejka je již vyskladněna")
            return HttpResponseRedirect(reverse_lazy('kitchen:showStockIssues',))
        return super(StockIssueDeleteView, self).post(request, *args, **kwargs)


class StockIssuePDFView(SuccessMessageMixin, LoginRequiredMixin, PDFTemplateView):
    template_name = 'kitchen/stockissue/pdf.html'
    filename = 'Vydejka.pdf'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        stock_issue = StockIssue.objects.filter(pk=self.kwargs['pk']).get()
        stock_issue_articles = StockIssueArticle.objects.filter(
            stock_issue_id=self.kwargs['pk']).order_by('article__article')
        context['stock_issue'] = stock_issue
        context['stock_issue_articles'] = stock_issue_articles
        context['title'] = "Výdejka"
        context['total_price'] = stock_issue.total_price
        return context


class StockIssueApproveView(LoginRequiredMixin, TemplateView):
    model = StockIssue
    template_name = 'kitchen/stockissue/approve.html'
    fields = "__all__"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        stock_issue = StockIssue.objects.filter(pk=self.kwargs['pk']).get()
        stock_issue_articles = StockIssueArticle.objects.filter(stock_issue_id=self.kwargs['pk'])
        context['stock_issue'] = stock_issue
        context['stock_issue_articles'] = stock_issue_articles
        context['total_price'] = stock_issue.total_price
        return context

    def post(self, *args, **kwargs):
        stock_issue = StockIssue.objects.filter(pk=self.kwargs['pk']).get()
        if stock_issue.approved:
            messages.warning(self.request, 'Vyskladnění neprovedeno - již bylo vyskladněno')
            return HttpResponseRedirect(reverse_lazy('kitchen:showStockIssues',))
        if stock_issue.total_price <= 0:
            messages.warning(
                self.request, 'Vyskladnění neprovedeno - nulová cena zboží, je zboží naskladněno?')
            return HttpResponseRedirect(reverse_lazy('kitchen:showStockIssues',))
        with transaction.atomic():
            stock_issue.approved = True
            stock_issue.date_approved = datetime.now()
            stock_issue.user_approved = self.request.user
            StockIssue.updateStockIssueArticleAverageUnitPrice(stock_issue.id)
            errors = StockIssue.updateArticleOnStock(stock_issue.id, True)
            if errors:
                errors = "Níže uvedené zboží není možné vyskladnit:<br/>" + errors
                messages.error(self.request, mark_safe(errors))
                return HttpResponseRedirect(reverse_lazy('kitchen:approveStockIssue', kwargs={'pk': self.kwargs['pk']}))
            _ = StockIssue.updateArticleOnStock(stock_issue.id, False)
            stock_issue.save(update_fields=('approved', 'date_approved', 'user_approved',))
            messages.success(self.request, "Výdejka byla vyskladněna")
            return HttpResponseRedirect(reverse_lazy('kitchen:showStockIssues',))


class StockIssueArticleListView(SingleTableMixin, LoginRequiredMixin, FilterView):
    model = StockIssueArticle
    table_class = StockIssueArticleTable
    template_name = 'kitchen/stockissue/listarticles.html'
    paginate_by = 15

    def get_context_data(self, **kwargs):
        context = super(StockIssueArticleListView, self).get_context_data(**kwargs)
        context['stockissue'] = StockIssue.objects.filter(pk=self.kwargs['pk']).get()
        return context

    def get_queryset(self):
        # show only StockIssueArticles
        return super().get_queryset().filter(stock_issue=self.kwargs["pk"]).order_by('article__article')


class StockIssueArticleCreateView(SuccessMessageMixin, LoginRequiredMixin, CreateView):
    model = StockIssueArticle
    form_class = StockIssueArticleForm
    template_name = 'kitchen/stockissue/createarticle.html'
    success_message = 'Zboží %(article)s bylo přidáno'

    def get_success_url(self):
        return reverse_lazy('kitchen:showStockIssueArticles', kwargs={'pk': self.kwargs['pk']})

    def get_context_data(self, **kwargs):
        context = super(StockIssueArticleCreateView, self).get_context_data(**kwargs)
        context['stockissue'] = StockIssue.objects.filter(pk=self.kwargs['pk']).get()
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        stock_issue = context['stockissue']
        stock_issue_article = form.save(commit=False)
        try:
            convertUnits(stock_issue_article.amount,
                         stock_issue_article.unit, stock_issue_article.article.unit)
        except ValidationError as err:
            messages.warning(self.request, err.message)
            return super(StockIssueArticleCreateView, self).form_invalid(form)
        stock_issue_article.stock_issue = StockIssue.objects.filter(pk=stock_issue.id).get()
        if stock_issue_article.stock_issue.approved:
            messages.warning(self.request, 'Přidání zboží neprovedeno, výdejka je již vyskladněna')
            return HttpResponseRedirect(
                reverse_lazy('kitchen:showStockIssueArticles', kwargs={'pk': stock_issue.id}))
        stock_issue_article.average_unit_price = stock_issue_article.article.average_price
        stock_issue_article.save()
        return super(StockIssueArticleCreateView, self).form_valid(form)


class StockIssueArticleUpdateView(SuccessMessageMixin, LoginRequiredMixin, UpdateView):
    model = StockIssueArticle
    form_class = StockIssueArticleForm
    template_name = 'kitchen/stockissue/updatearticle.html'
    success_message = "Zboží %(article)s bylo aktualizováno"

    def get_success_url(self):
        return reverse_lazy('kitchen:showStockIssueArticles', kwargs={'pk': self.kwargs['pk']})

    def get_context_data(self, **kwargs):
        context = super(StockIssueArticleUpdateView, self).get_context_data(**kwargs)
        context['stock_issue_article_before'] = StockIssueArticle.objects.filter(pk=self.kwargs['pk']).get()
        return context

    def form_valid(self, form):
        stock_issue_article = form.save(commit=False)
        try:
            convertUnits(stock_issue_article.amount,
                         stock_issue_article.unit, stock_issue_article.article.unit)
        except ValidationError as err:
            messages.warning(self.request, err.message)
            return super(StockIssueArticleUpdateView, self).form_invalid(form)
        stock_issue_article.stock_issue = StockIssueArticle.objects.filter(pk=stock_issue_article.id).get().stock_issue
        if stock_issue_article.stock_issue.approved:
            messages.warning(self.request, 'Aktualizace zboží neprovedena, výdejka je již vyskladněna')
            return HttpResponseRedirect(
                reverse_lazy('kitchen:showStockIssueArticles', kwargs={'pk': stock_issue_article.stock_issue.id}))
        stock_issue_article.average_unit_price = stock_issue_article.article.average_price
        stock_issue_article.save()
        self.kwargs = {'pk': stock_issue_article.stock_issue.id}
        return super(StockIssueArticleUpdateView, self).form_valid(form)


class StockIssueArticleDeleteView(SuccessMessageMixin, LoginRequiredMixin, DeleteView):
    model = StockIssueArticle
    template_name = 'kitchen/stockissue/deletearticle.html'
    success_message = "Zboží bylo odstraněno"
    success_url = reverse_lazy('kitchen:showStockIssues')
    stock_issue_id = 0

    def get_success_url(self):
        return reverse_lazy('kitchen:showStockIssueArticles', kwargs={'pk': self.stock_issue_id})

    def delete(self, request, *args, **kwargs):
        stock_issue_article = get_object_or_404(StockIssueArticle, pk=self.kwargs['pk'])
        if stock_issue_article.stock_issue.approved:
            messages.warning(self.request, 'Odstranění zboží neprovedeno, výdejka je již vyskladněna')
            return HttpResponseRedirect(
                reverse_lazy('kitchen:showStockIssueArticles', kwargs={'pk': stock_issue_article.stock_issue.id}))
        self.stock_issue_id = stock_issue_article.stock_issue.id
        return super(StockIssueArticleDeleteView, self).delete(request, *args, **kwargs)


class StockReceiptListView(SingleTableMixin, LoginRequiredMixin, FilterView):
    model = StockReceipt
    table_class = StockReceiptTable
    template_name = 'kitchen/stockreceipt/list.html'
    filterset_class = StockReceiptFilter
    form_class = StockReceiptSearchForm
    paginate_by = 12


class StockReceiptCreateView(SuccessMessageMixin, LoginRequiredMixin, CreateView):
    model = StockReceipt
    form_class = StockReceiptForm
    template_name = 'kitchen/stockreceipt/create.html'
    success_message = "Příjemka byla vytvořena a je možné přidávat zboží"

    def form_valid(self, form):
        form.instance.user_created = self.request.user
        self.object = form.save()
        return super(StockReceiptCreateView, self).form_valid(form)

    def get_success_url(self):
        return reverse_lazy('kitchen:createStockReceiptArticle', kwargs={'pk': self.object.id})


class StockReceiptUpdateView(SuccessMessageMixin, LoginRequiredMixin, UpdateView):
    model = StockReceipt
    form_class = StockReceiptForm
    template_name = 'kitchen/stockreceipt/update.html'
    success_message = "Poznámka příjemky byla aktualizována"
    success_url = reverse_lazy('kitchen:showStockReceipts')


class StockReceiptDeleteView(SuccessMessageMixin, LoginRequiredMixin, DeleteView):
    model = StockReceipt
    template_name = 'kitchen/stockreceipt/delete.html'
    success_message = "Příjemka ze dne %(created)s byla odstraněna"
    success_url = reverse_lazy('kitchen:showStockReceipts')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        stock_receipt = StockReceipt.objects.filter(pk=self.kwargs['pk']).get()
        stock_receipt_articles = StockReceiptArticle.objects.filter(stock_receipt_id=self.kwargs['pk'])
        context['stock_receipt'] = stock_receipt
        context['stock_receipt_articles'] = stock_receipt_articles
        context['total_price'] = stock_receipt.total_price
        return context

    def post(self, request, *args, **kwargs):
        stock_receipt = StockReceipt.objects.filter(pk=self.kwargs['pk']).get()
        if stock_receipt.approved:
            messages.warning(self.request, "Výmaz neproveden - příjemka je již naskladněna")
            return HttpResponseRedirect(reverse_lazy('kitchen:showStockReceipts',))
        return super(StockReceiptDeleteView, self).post(request, *args, **kwargs)


class StockReceiptPDFView(LoginRequiredMixin, PDFTemplateView):
    template_name = 'kitchen/stockreceipt/pdf.html'
    filename = 'Prijemka.pdf'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        stock_receipt = StockReceipt.objects.filter(pk=self.kwargs['pk']).get()
        stock_receipt_articles = StockReceiptArticle.objects.filter(stock_receipt_id=self.kwargs['pk'])
        context['stock_receipt'] = stock_receipt
        context['stock_receipt_articles'] = stock_receipt_articles
        context['title'] = "Příjemka"
        context['total_price'] = stock_receipt.total_price
        return context


class StockReceiptApproveView(LoginRequiredMixin, TemplateView):
    model = StockReceipt
    template_name = 'kitchen/stockreceipt/approve.html'
    fields = "__all__"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        stock_receipt = StockReceipt.objects.filter(pk=self.kwargs['pk']).get()
        stock_receipt_articles = StockReceiptArticle.objects.filter(stock_receipt_id=self.kwargs['pk'])
        context['stock_receipt'] = stock_receipt
        context['stock_receipt_articles'] = stock_receipt_articles
        context['total_price'] = stock_receipt.total_price
        return context

    def post(self, *args, **kwargs):
        stock_receipt = StockReceipt.objects.filter(pk=self.kwargs['pk']).get()
        if stock_receipt.approved:
            messages.warning(self.request, 'Naskladnění neprovedeno - již bylo naskladněno')
            return HttpResponseRedirect(reverse_lazy('kitchen:showStockReceipts',))
        if stock_receipt.total_price <= 0:
            messages.warning(
                self.request, 'Naskladnění neprovedeno - nulová cena zboží, přidejte alespoň jedno zboží na příjemku')
            return HttpResponseRedirect(reverse_lazy('kitchen:showStockReceipts',))
        with transaction.atomic():
            stock_receipt.approved = True
            stock_receipt.date_approved = datetime.now()
            stock_receipt.user_approved = self.request.user
            StockReceipt.updateArticleOnStock(stock_receipt.id)
            stock_receipt.save(update_fields=('approved', 'date_approved', 'user_approved',))
            messages.success(self.request, "Příjemka byla naskladněna")
        return HttpResponseRedirect(reverse_lazy('kitchen:showStockReceipts',))


class StockReceiptArticleListView(SingleTableMixin, LoginRequiredMixin, FilterView):
    model = StockReceiptArticle
    table_class = StockReceiptArticleTable
    template_name = 'kitchen/stockreceipt/listarticles.html'
    paginate_by = 15

    def get_context_data(self, **kwargs):
        context = super(StockReceiptArticleListView, self).get_context_data(**kwargs)
        context['stockreceipt'] = StockReceipt.objects.filter(pk=self.kwargs['pk']).get()
        return context

    def get_queryset(self):
        # show only StockReceiptArticles
        return super().get_queryset().filter(stock_receipt=self.kwargs["pk"])


class StockReceiptArticleCreateView(SuccessMessageMixin, LoginRequiredMixin, CreateView):
    model = StockReceiptArticle
    form_class = StockReceiptArticleForm
    template_name = 'kitchen/stockreceipt/createarticle.html'
    success_message = 'Zboží %(article)s bylo přidáno'

    def get_success_url(self):
        return reverse_lazy('kitchen:createStockReceiptArticle', kwargs={'pk': self.kwargs['pk']})

    def get_context_data(self, **kwargs):
        context = super(StockReceiptArticleCreateView, self).get_context_data(**kwargs)
        context['stockreceipt'] = StockReceipt.objects.filter(pk=self.kwargs['pk'])[0]
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        stock_receipt = context['stockreceipt']
        stock_receipt_article = form.save(commit=False)
        try:
            convertUnits(stock_receipt_article.amount,
                         stock_receipt_article.unit, stock_receipt_article.article.unit)
        except ValidationError as err:
            messages.warning(self.request, err.message)
            return super(StockReceiptArticleCreateView, self).form_invalid(form)
        stock_receipt_article.stock_receipt = StockReceipt.objects.filter(pk=stock_receipt.id).get()
        if stock_receipt_article.stock_receipt.approved:
            messages.warning(self.request, 'Přidání zboží neprovedeno, příjemka je již naskladněna')
            return HttpResponseRedirect(
                reverse_lazy('kitchen:showStockReceiptArticles', kwargs={'pk': stock_receipt.id}))
        stock_receipt_article.save()
        return super(StockReceiptArticleCreateView, self).form_valid(form)


class StockReceiptArticleUpdateView(SuccessMessageMixin, LoginRequiredMixin, UpdateView):
    model = StockReceiptArticle
    form_class = StockReceiptArticleForm
    template_name = 'kitchen/stockreceipt/updatearticle.html'
    success_message = "Zboží %(article)s bylo aktualizováno"

    def get_success_url(self):
        return reverse_lazy('kitchen:showStockReceiptArticles', kwargs={'pk': self.kwargs['pk']})

    def get_context_data(self, **kwargs):
        context = super(StockReceiptArticleUpdateView, self).get_context_data(**kwargs)
        context['stock_receipt_article_before'] = StockReceiptArticle.objects.filter(pk=self.kwargs['pk']).get()
        return context

    def form_valid(self, form):
        stock_receipt_article = form.save(commit=False)
        try:
            convertUnits(stock_receipt_article.amount,
                         stock_receipt_article.unit, stock_receipt_article.article.unit)
        except ValidationError as err:
            messages.warning(self.request, err.message)
            return super(StockReceiptArticleUpdateView, self).form_invalid(form)
        stock_receipt_article.stock_receipt = StockReceiptArticle.objects.filter(
            pk=stock_receipt_article.id).get().stock_receipt
        if stock_receipt_article.stock_receipt.approved:
            messages.warning(self.request, 'Aktualizace zboží neprovedena, příjemka je již naskladněna')
            return HttpResponseRedirect(
                reverse_lazy('kitchen:showStockReceiptArticles', kwargs={'pk': stock_receipt_article.stock_receipt.id}))
        stock_receipt_article.save()
        self.kwargs = {'pk': stock_receipt_article.stock_receipt.id}
        return super(StockReceiptArticleUpdateView, self).form_valid(form)


class StockReceiptArticleDeleteView(SuccessMessageMixin, LoginRequiredMixin, DeleteView):
    model = StockReceiptArticle
    template_name = 'kitchen/stockreceipt/deletearticle.html'
    success_message = "Zboží bylo odstraněno"
    success_url = reverse_lazy('kitchen:showStockReceipts')
    stock_receipt_id = 0

    def get_success_url(self):
        return reverse_lazy('kitchen:showStockReceiptArticles', kwargs={'pk': self.stock_receipt_id})

    def delete(self, request, *args, **kwargs):
        stock_receipt_article = get_object_or_404(StockReceiptArticle, pk=self.kwargs['pk'])
        if stock_receipt_article.stock_receipt.approved:
            messages.warning(self.request, 'Odstranění zboží neprovedeno, příjemka je již naskladněna')
            return HttpResponseRedirect(
                reverse_lazy('kitchen:showStockReceiptArticles', kwargs={'pk': self.kwargs['pk']}))
        self.stock_receipt_id = stock_receipt_article.stock_receipt.id
        return super(StockReceiptArticleDeleteView, self).delete(request, *args, **kwargs)


class FoodConsumptionPDFView(LoginRequiredMixin, PDFTemplateView):
    template_name = 'kitchen/report/food_consumption_pdf.html'
    filename = 'Spotreba_potravin.pdf'

    def get(self, request, *args, **kwargs):
        try:
            date = request.GET['date']
            datetime.strptime(date, "%d.%m.%Y")
        except ValueError as e:
            messages.warning(self.request, "Chybně zadané datum. Požadovaný formát je dd.mm.rr. Chyba: {}".format(e))
            return HttpResponseRedirect(reverse_lazy('kitchen:filterFoodConsumption'))
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        date = self.request.GET['date']
        meal_group = self.request.GET['meal_group']
        # typ jidla (snidane i bc)
        # # recept, počet ks
        # # # article, množství
        if len(meal_group) == 0:
            daily_menus = DailyMenu.objects.filter(date=datetime.strptime(date, "%d.%m.%Y"))
        else:
            daily_menus = DailyMenu.objects.filter(date=datetime.strptime(
                date, "%d.%m.%Y"), meal_group=meal_group)
            context['meal_group_filter'] = "Filtrováno pro skupinu strávníků: " + \
                MealGroup.objects.filter(pk=meal_group).get().meal_group

        output = []
        for daily_menu in daily_menus:
            # for recipe in daily_menu
            dmrs = DailyMenuRecipe.objects.filter(daily_menu=daily_menu).select_related('recipe')
            daily_menu_recipes = []
            for dmr in dmrs:
                ras = RecipeArticle.objects.filter(recipe=dmr.recipe).select_related('article')
                daily_menu_recipe_articles = []
                for ra in ras:
                    daily_menu_recipe_article = {
                        "article": ra.article,
                        "amount": round(ra.amount * dmr.amount / ra.recipe.norm_amount, 2),  # konverze amount
                        "unit": ra.unit
                    }
                    daily_menu_recipe_articles.append(daily_menu_recipe_article)
                daily_menu_recipe = {
                    "name": dmr.recipe,
                    "amount": dmr.amount,
                    "articles": daily_menu_recipe_articles
                }
                daily_menu_recipes.append(daily_menu_recipe)
            output_new = {
                "meal_type": daily_menu.meal_type,
                "recipes": daily_menu_recipes
            }
            output.append(output_new)

        # output_dedup = []
        # for daily_menu in daily_menus:
        #     # for recipe in daily_menu
        #     dmrs = DailyMenuRecipe.objects.filter(daily_menu=daily_menu).select_related('recipe')
        #     daily_menu_recipes = []
        #     for dmr in dmrs:
        #         ras = RecipeArticle.objects.filter(recipe=dmr.recipe).select_related('article')
        #         daily_menu_recipe_articles = []
        #         for ra in ras:
        #             daily_menu_recipe_article = {
        #                 "article": ra.article,
        #                 "amount": round(ra.amount * dmr.amount / ra.recipe.norm_amount, 2),  # konverze amount
        #                 "unit": ra.unit
        #             }
        #             daily_menu_recipe_articles.append(daily_menu_recipe_article)
        #         daily_menu_recipe = {
        #             "name": dmr.recipe,
        #             "amount": dmr.amount,
        #             "articles": daily_menu_recipe_articles
        #         }
        #         daily_menu_recipes.append(daily_menu_recipe)
        #     output_new = {
        #         "meal_type": daily_menu.meal_type,
        #         "recipes": daily_menu_recipes
        #     }
        #     # deduplikace dle meal type
        #     # pak dle receptu, spočíst amount
        #     # pak dle ingrediencií - spočíst amount
        #     dup = False
        #     for dmn in output_dedup:
        #         if output_new['meal_type'] == dmn['meal_type']:
        #             dup = True
        #             print("duplicitaXXX:", output_new['meal_type'])
        #             dmn['recipes'].append(daily_menu_recipes)
        #             # add amount to the existing recipe or insert new recipe
        #             # for recipe in dmn['recipes']:
        #             #     for recipe_new in output_new['recipes']:
        #             #         found = False
        #             #         if recipe['name'] == recipe_new['name']:
        #             #             found = True
        #             #             break
        #             #             # add ingredient amount
        #             #     if found:
        #             #         print("same recipe", output_new['meal_type'], recipe['name'], recipe['amount'])
        #             #     else:
        #             #         print("adding recipe", output_new['meal_type'], recipe['name'], recipe['amount'])
        #     if not dup:
        #         output_dedup.append(output_new)

        context['title'] = "Rozpis pro kuchyň dle receptur na den " + date
        context['daily_menus'] = output
        # context['daily_menus_dedup'] = output_dedup
        return context


class FoodConsumptionPrintView(LoginRequiredMixin, CreateView):
    model = DailyMenu
    form_class = FoodConsumptionPrintForm
    template_name = 'kitchen/report/food_consumption.html'


class IncorrectUnitsListView(SingleTableMixin, LoginRequiredMixin, ListView):
    model = Recipe
    template_name = 'kitchen/report/incorrect-units.html'

    def get_queryset(self):
        # show only recipes where article unit cannot be converted to stock article unit
        recipes = super().get_queryset()
        incorrect_recipes = set()
        for recipe in recipes:
            recipe_articles = RecipeArticle.objects.filter(recipe=recipe)
            for recipe_article in recipe_articles:
                try:
                    convertUnits(recipe_article.amount,
                                 recipe_article.unit, recipe_article.article.unit)
                except ValidationError:
                    incorrect_recipes.add(recipe.pk)
        return Recipe.objects.filter(pk__in=incorrect_recipes)


class ArticlesNotInRecipesListView(SingleTableMixin, LoginRequiredMixin, ListView):
    model = Article
    template_name = 'kitchen/report/articles_not_in_recipe.html'

    def get_context_data(self, *, object_list=None, **kwargs):
        context = super().get_context_data(**kwargs)
        articles_on_recipes = RecipeArticle.objects.values_list('article__id')
        articles = Article.objects.exclude(pk__in=articles_on_recipes)
        context['articles'] = articles
        return context
