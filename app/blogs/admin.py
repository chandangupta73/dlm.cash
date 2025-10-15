from django.contrib import admin
from .models import Category, SubCategory, Blog

@admin.register(SubCategory)
class SubCategoryAdmin(admin.ModelAdmin):
    list_display = ('sub_category', 'category', 'slug', 'status', 'order')
    list_filter = ('status', 'category')
    search_fields = ('sub_category', 'category__category')
    ordering = ('order',)
    exclude = ('slug',)
    list_editable = ('status',)
    # autocomplete_fields = ['author']


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('category', 'slug', 'status', 'order')
    list_filter = ('status',)
    search_fields = ('category',)
    ordering = ('order',)
    exclude = ('slug',)
    list_editable = ('status',)


@admin.register(Blog)
class BlogAdmin(admin.ModelAdmin):
    list_display = ('blog_title', 'blog_category', 'author', 'status', 'blog_date', 'updated_at', 'viewcounter', 'order')
    list_filter = ('status', 'blog_category', 'author')
    search_fields = ('blog_title', 'blog_short_des', 'blog_des', 'blog_category__sub_category', 'author__username')
    ordering = ('-blog_date',)
    autocomplete_fields = ['author', 'blog_category']
    date_hierarchy = 'blog_date'
    exclude = ('slug',)
    readonly_fields = ['viewcounter'] 
    list_editable = ('status',)
