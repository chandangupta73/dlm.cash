from django.db import models
from autoslug import AutoSlugField
from ckeditor_uploader.fields import RichTextUploadingField
from django.urls import reverse
from django.conf import settings

class Category(models.Model):
    category = models.CharField(max_length=255, unique=True, null=True, blank=True, default=None, verbose_name="Category Name")
    slug = AutoSlugField(populate_from='category', unique=True, null=True, blank=True, default=None)
    STATUS_CHOICES = (('active', 'Active'), ('inactive', 'Inactive'))
    status = models.CharField(max_length=8, choices=STATUS_CHOICES, default='active', verbose_name="Status")
    order = models.IntegerField(unique=True, null=True, blank=True, default=None, verbose_name="Order")

    class Meta:
        verbose_name_plural = "Categories"
        ordering = ['order']

    def __str__(self): return self.category or ""


class SubCategory(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE, null=True, blank=True, default=None, verbose_name="Select Category")
    sub_category = models.CharField(max_length=255, unique=True, null=True, blank=True, default=None)
    slug = AutoSlugField(populate_from='sub_category', unique=True, null=True, blank=True, default=None)
    STATUS_CHOICES = (('active', 'Active'), ('inactive', 'Inactive'))
    status = models.CharField(max_length=8, choices=STATUS_CHOICES, default='active', verbose_name="Status")
    order = models.IntegerField(unique=True, null=True, blank=True, default=None, verbose_name="Order")

    class Meta:
        verbose_name_plural = "Subcategories"
        ordering = ['order']

    def __str__(self): return f"{self.category} / {self.sub_category}"


class Blog(models.Model):
    slug = AutoSlugField(max_length=200, populate_from='blog_title', unique=True, null=True, blank=True, default=None)
    blog_category = models.ForeignKey(SubCategory, on_delete=models.CASCADE, null=True, blank=True, default=None, verbose_name="Select Category")
    blog_title = models.CharField(max_length=150, verbose_name="blog Headline", null=True, blank=True, default=None)
    blog_short_des = models.CharField(max_length=160, verbose_name="Short Description", null=True, blank=True, default=None)
    blog_des = RichTextUploadingField(null=True, blank=True, default='No blog', verbose_name="Long Description")
    blog_image = models.ImageField(upload_to='media/%Y/%m/%d', null=True, blank=True, default=None, verbose_name="Blog Image (1280x720px)")
    viewcounter = models.IntegerField(default=0, verbose_name="Views")
    counter = models.IntegerField(default=100, verbose_name="Added Views")
    blog_date = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    order = models.IntegerField(default=5, verbose_name="Order")
    STATUS_CHOICES = (('active', 'Active'), ('inactive', 'Inactive'))
    status = models.CharField(max_length=8, choices=STATUS_CHOICES, default='active')
    author = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,null=True, blank=True, default=None)

    class Meta:
        ordering = ['-blog_date']

    def __str__(self): return self.blog_title or ""

    def get_absolute_url(self): return reverse('blogdetails', args=[self.slug])
