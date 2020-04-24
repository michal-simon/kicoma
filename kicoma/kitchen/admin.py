from import_export import resources
from import_export.admin import ImportExportActionModelAdmin
from django.contrib import admin
from . models import StockUnit, StockItem, Allergen, MealType, Recipe, RecipeIngredient, TargetGroup, VAT, DailyMenu

# create import export resources


class VATResource(resources.ModelResource):

    class Meta:
        model = VAT
        skip_unchanged = True
        report_skipped = True


class AllergenResource(resources.ModelResource):

    class Meta:
        model = Allergen
        skip_unchanged = True
        report_skipped = True


class StockItemResource(resources.ModelResource):

    class Meta:
        model = StockItem
        skip_unchanged = True
        report_skipped = True


class MealTypeResource(resources.ModelResource):

    class Meta:
        model = MealType
        skip_unchanged = True
        report_skipped = True


class DailyMenuResource(resources.ModelResource):

    class Meta:
        model = DailyMenu
        skip_unchanged = True
        report_skipped = True


class RecipeResource(resources.ModelResource):

    class Meta:
        model = Recipe
        skip_unchanged = True
        report_skipped = True


class RecipeIngredientResource(resources.ModelResource):

    class Meta:
        model = RecipeIngredient
        skip_unchanged = True
        report_skipped = True


class TargetGroupResource(resources.ModelResource):

    class Meta:
        model = TargetGroup
        skip_unchanged = True
        report_skipped = True


class StockUnitResource(resources.ModelResource):

    class Meta:
        model = StockUnit
        skip_unchanged = True
        report_skipped = True

# integrate import export into admin


class AllergenAdmin(ImportExportActionModelAdmin):
    list_display = ('code', 'description',)
    ordering = ('code',)
    resource_class = AllergenResource


class VATAdmin(ImportExportActionModelAdmin):
    list_display = ('percentage', 'name',)
    ordering = ('-percentage',)
    resource_class = VATResource


class StockUnitAdmin(ImportExportActionModelAdmin):
    list_display = ('name',)
    ordering = ('name',)
    resource_class = StockUnitResource


class TargetGroupAdmin(ImportExportActionModelAdmin):
    list_display = ('name',)
    ordering = ('name',)
    resource_class = TargetGroupResource


class MealTypeAdmin(ImportExportActionModelAdmin):
    list_display = ('name', 'category')
    ordering = ('category',)
    resource_class = MealTypeResource


class DailyMenuAdmin(ImportExportActionModelAdmin):
    list_display = ('date', 'amount', 'targetGroup', 'mealType')
    # ordering = ('category',)
    resource_class = DailyMenuResource


class StockItemAdmin(ImportExportActionModelAdmin):
    list_display = ('name', 'unit', 'coefficient', 'normPrice', 'averagePrice', 'display_allergens', 'comment', )
    fields = [('name', 'unit', 'coefficient'), ('normPrice', 'averagePrice', 'criticalAmount'), 'allergen', 'comment', ]
    list_filter = ('unit', 'coefficient')
    search_fields = ('name',)
    resource_class = StockItemResource


class RecipeAdmin(ImportExportActionModelAdmin):
    list_display = ('name', 'norm_amount', 'comment', 'recipeIngredient',)
    resource_class = RecipeResource


class RecipeIngredientAdmin(ImportExportActionModelAdmin):
    list_display = ('amount', 'stockItem',)
    resource_class = RecipeIngredientResource


admin.site.register(Allergen, AllergenAdmin)
admin.site.register(VAT, VATAdmin)
admin.site.register(StockUnit, StockUnitAdmin)
admin.site.register(TargetGroup, TargetGroupAdmin)
admin.site.register(MealType, MealTypeAdmin)
admin.site.register(RecipeIngredient, RecipeIngredientAdmin)
admin.site.register(Recipe, RecipeAdmin)
admin.site.register(DailyMenu, DailyMenuAdmin)

admin.site.register(StockItem, StockItemAdmin)
