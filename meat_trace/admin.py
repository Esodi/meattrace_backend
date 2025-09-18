from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from .models import UserProfile, Animal, Product, Receipt

# Register your models here.

class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Profile'

class CustomUserAdmin(UserAdmin):
    inlines = (UserProfileInline,)

# Re-register UserAdmin
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)

@admin.register(Animal)
class AnimalAdmin(admin.ModelAdmin):
    list_display = ('id', 'farmer', 'species', 'age', 'weight', 'created_at', 'slaughtered', 'slaughtered_at')
    search_fields = ('farmer__username', 'species')
    list_filter = ('species', 'slaughtered', 'created_at')

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('id', 'processing_unit', 'animal', 'product_type', 'quantity', 'created_at')
    search_fields = ('processing_unit__username', 'product_type', 'animal__species')
    list_filter = ('product_type', 'created_at')

@admin.register(Receipt)
class ReceiptAdmin(admin.ModelAdmin):
    list_display = ('id', 'shop', 'product', 'received_quantity', 'received_at')
    search_fields = ('shop__username', 'product__product_type')
    list_filter = ('received_at',)
