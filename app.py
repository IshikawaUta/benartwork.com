from flask import Flask, render_template, request, redirect, url_for, flash, make_response
from pymongo import MongoClient
import cloudinary
from cloudinary.uploader import upload
from cloudinary.utils import cloudinary_url
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, DecimalField, FileField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Length, NumberRange
from config import Config
import os
from datetime import datetime
from math import ceil
from bson.objectid import ObjectId
from flask_mail import Mail, Message # Import Flask-Mail
from wtforms import StringField, TextAreaField, DecimalField, FileField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Length, NumberRange, Email
import logging
import sys

app = Flask(__name__)
app.config.from_object(Config)
mail = Mail(app)

if app.logger.handlers:
    for handler in app.logger.handlers:
        app.logger.removeHandler(handler)

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(logging.Formatter(
    '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'))
console_handler.setLevel(logging.INFO)
app.logger.addHandler(console_handler)

app.logger.setLevel(logging.INFO)
app.logger.info('Benartwork app starting on Vercel')

# MongoDB Setup
# Pastikan MONGO_URI di config.py sudah benar
client = MongoClient(app.config['MONGO_URI'])
db = client.benartwork_db # <--- Ganti dengan nama database Anda di MongoDB Atlas
products_collection = db.products
blog_collection = db.blog
users_collection = db.users # Untuk manajemen user admin

# Cloudinary Setup
cloudinary.config(
    cloud_name=app.config['CLOUDINARY_CLOUD_NAME'],
    api_key=app.config['CLOUDINARY_API_KEY'],
    api_secret=app.config['CLOUDINARY_API_SECRET']
)

# Flask-Login Setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'admin_login'
login_manager.login_message_category = 'info' # Kategori pesan flash saat login diperlukan

class User(UserMixin):
    def __init__(self, user_id):
        self.id = user_id

    @staticmethod
    def get(user_id):
        # Menggunakan str(user_id) karena ObjectId dari MongoDB perlu dikonversi ke string
        # dan saat mencari kembali, perlu dikonversi ke ObjectId lagi
        try:
            user_data = users_collection.find_one({"_id": ObjectId(user_id)})
            if user_data:
                return User(str(user_data['_id']))
            return None
        except Exception:
            return None

@login_manager.user_loader
def load_user(user_id):
    return User.get(user_id)

# --- Forms (Flask-WTF) ---
class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=4, max=20)])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

class ProductForm(FlaskForm):
    name = StringField('Product Name', validators=[DataRequired(), Length(min=3, max=100)])
    description = TextAreaField('Description', validators=[DataRequired()])
    price = DecimalField('Price', validators=[DataRequired(), NumberRange(min=0.01)])
    image = FileField('Product Image')
    submit = SubmitField('Save Product')

class BlogPostForm(FlaskForm):
    title = StringField('Title', validators=[DataRequired(), Length(min=3, max=200)])
    content = TextAreaField('Content', validators=[DataRequired()])
    author = StringField('Author', validators=[DataRequired(), Length(min=3, max=50)])
    image = FileField('Blog Image')
    submit = SubmitField('Save Post')

# --- Contact Form ---
class ContactForm(FlaskForm):
    name = StringField('Nama Lengkap', validators=[DataRequired(), Length(min=2, max=100)])
    email = StringField('Alamat Email', validators=[DataRequired(), Email()])
    subject = StringField('Subjek', validators=[DataRequired(), Length(min=5, max=200)])
    message = TextAreaField('Pesan Anda', validators=[DataRequired(), Length(min=10)])
    submit = SubmitField('Kirim Pesan')

# --- Routes ---

# Header Flask
@app.after_request
def add_header(response):
    response.headers['X-Powered-By'] = 'Flask'
    return response

# Public Routes
@app.route('/')
def index():
    products = list(products_collection.find().limit(4)) # Konversi ke list di sini
    recent_posts = list(blog_collection.find().sort("date", -1).limit(3))
    seo_data = {
        'title': 'Home - Benartwork',
        'description': 'Discover captivating digital illustrations and traditional art by Benartwork. Specializing in character design, editorial art, and custom commissions. Bring your vision to life with unique artwork.',
        'keywords': 'Benartwork, benartwork777, Freelancer, Illustrator, art, digital illustrations, traditional art, character design, editorial art, custom commissions'
    }
    return render_template('index.html', products=products, recent_posts=recent_posts, seo=seo_data)

@app.route('/products')
def products():
    page = request.args.get('page', 1, type=int)
    per_page = app.config['PRODUCTS_PER_PAGE']
    skip = (page - 1) * per_page

    total_products = products_collection.count_documents({})
    all_products = products_collection.find().skip(skip).limit(per_page)
    total_pages = ceil(total_products / per_page)

    seo_data = {
        'title': 'Products - Benartwork',
        'description': f'Jelajahi koleksi produk-produk berkualitas tinggi dari Benartwork. Halaman {page} dari {total_pages}.',
        'keywords': 'produk, koleksi, art, illustrator'
    }

    return render_template('products.html',
                           products=all_products,
                           page=page,
                           total_pages=total_pages,
                           per_page=per_page,
                           seo=seo_data)

@app.route('/product/<product_id>')
def product_detail(product_id):
    try:
        product = products_collection.find_one({"_id": ObjectId(product_id)})
        if product:
            seo_data = {
                'title': f"{product.get('name', 'Detail Produk')} - Benartwork",
                'description': product.get('description', '')[:160] + '...',
                'keywords': f"produk, {product.get('name', '')}, beli, harga"
            }
            return render_template('product_detail.html', product=product, seo=seo_data)
        else:
            flash('Produk tidak ditemukan.', 'danger')
            app.logger.warning(f"Product not found for ID: {product_id}")
            return redirect(url_for('products'))
    except Exception as e:
        app.logger.error(f"Invalid product ID or database error for ID {product_id}: {e}", exc_info=True)
        flash('Terjadi kesalahan saat memuat detail produk. ID tidak valid.', 'danger')
        return redirect(url_for('products'))

@app.route('/blog')
def blog():
    page = request.args.get('page', 1, type=int)
    per_page = app.config['POSTS_PER_PAGE']
    skip = (page - 1) * per_page

    total_posts = blog_collection.count_documents({})
    all_posts = blog_collection.find().sort("date", -1).skip(skip).limit(per_page) # Diurutkan berdasarkan tanggal terbaru
    total_pages = ceil(total_posts / per_page)

    seo_data = {
        'title': 'Blog - Benartwork',
        'description': f'Baca artikel dan berita terbaru dari blog Benartwork. Halaman {page} dari {total_pages}.',
        'keywords': 'blog, artikel, berita, informasi, tips'
    }

    return render_template('blog.html',
                           posts=all_posts,
                           page=page,
                           total_pages=total_pages,
                           per_page=per_page,
                           seo=seo_data)

@app.route('/blog/<post_id>')
def blog_post(post_id):
    try:
        post = blog_collection.find_one({"_id": ObjectId(post_id)})
        if post:
            seo_data = {
                'title': f"{post.get('title', 'Postingan Blog')} - Benartwork Blog",
                'description': post.get('content', '')[:160] + '...',
                'keywords': f"blog, {post.get('title', '')}, {post.get('author', '')}, artikel"
            }
            return render_template('blog_post.html', post=post, seo=seo_data)
        else:
            flash('Postingan blog tidak ditemukan.', 'danger')
            app.logger.warning(f"Blog post not found for ID: {post_id}")
            return redirect(url_for('blog'))
    except Exception as e:
        app.logger.error(f"Invalid blog post ID or database error for ID {post_id}: {e}", exc_info=True)
        flash('Terjadi kesalahan saat memuat postingan blog. ID tidak valid.', 'danger')
        return redirect(url_for('blog'))

@app.route('/about')
def about():
    seo_data = {
        'title': 'About Us - Benartwork',
        'description': 'Pelajari lebih lanjut tentang Benartwork, misi, dan tim kami.',
        'keywords': 'tentang kami, misi, visi, tim'
    }
    return render_template('about.html', seo=seo_data)

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    form = ContactForm()
    if form.validate_on_submit():
        # Kirim Email
        msg = Message(
            subject=f"Pesan Kontak: {form.subject.data}",
            sender=app.config['MAIL_DEFAULT_SENDER'],
            recipients=[app.config['ADMIN_EMAIL']]
        )
        msg.body = f"""
Dari: {form.name.data} <{form.email.data}>
Subjek: {form.subject.data}

Pesan:
{form.message.data}
"""
        try:
            mail.send(msg)
            flash('Pesan Anda telah berhasil terkirim! Kami akan segera menghubungi Anda.', 'success')
            return redirect(url_for('contact'))
        except Exception as e:
            flash(f'Terjadi kesalahan saat mengirim pesan Anda: {e}', 'danger')

    seo_data = {
        'title': 'Contact Us - Benartwork',
        'description': 'Kirim pesan kepada kami atau temukan informasi kontak Benartwork.',
        'keywords': 'kontak, hubungi, email, telepon, alamat'
    }
    return render_template('contact.html', form=form, seo=seo_data)

# Admin Routes
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    form = LoginForm()
    if form.validate_on_submit():
        user = users_collection.find_one({"username": form.username.data})
        if user and check_password_hash(user['password'], form.password.data):
            login_user(User(str(user['_id'])))
            flash('Login berhasil!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('admin_dashboard'))
        else:
            flash('Login gagal. Periksa username dan password Anda.', 'danger')
    return render_template('admin/login.html', form=form)

@app.route('/admin/logout')
@login_required
def admin_logout():
    logout_user()
    flash('Anda telah keluar.', 'info')
    return redirect(url_for('admin_login'))

@app.route('/admin')
@login_required
def admin_dashboard():
    return render_template('admin/dashboard.html')

# --- Product Management ---
@app.route('/admin/products')
@login_required
def manage_products():
    products = products_collection.find()
    return render_template('admin/manage_products.html', products=products)

@app.route('/admin/products/add', methods=['GET', 'POST'])
@login_required
def add_product():
    form = ProductForm()
    if form.validate_on_submit():
        image_url = None
        if form.image.data:
            try:
                upload_result = upload(form.image.data, folder="your_website_products") # Ganti dengan folder Cloudinary Anda
                image_url = upload_result['secure_url']
            except Exception as e:
                flash(f'Gagal mengunggah gambar ke Cloudinary: {e}', 'danger')
                return render_template('admin/add_product.html', form=form)

        new_product = {
            "name": form.name.data,
            "description": form.description.data,
            "price": float(form.price.data),
            "image_url": image_url
        }
        products_collection.insert_one(new_product)
        flash('Produk berhasil ditambahkan!', 'success')
        return redirect(url_for('manage_products'))
    return render_template('admin/add_product.html', form=form)

@app.route('/admin/products/edit/<product_id>', methods=['GET', 'POST'])
@login_required
def edit_product(product_id):
    try:
        product = products_collection.find_one({"_id": ObjectId(product_id)})
        if not product:
            flash('Produk tidak ditemukan.', 'danger')
            return redirect(url_for('manage_products'))

        form = ProductForm(obj=product) # Pre-populate form with existing data
        if form.validate_on_submit():
            image_url = product.get('image_url') # Keep existing image if no new one uploaded
            if form.image.data:
                try:
                    upload_result = upload(form.image.data, folder="your_website_products")
                    image_url = upload_result['secure_url']
                except Exception as e:
                    flash(f'Gagal mengunggah gambar ke Cloudinary: {e}', 'danger')
                    return render_template('admin/edit_product.html', form=form, product=product)

            products_collection.update_one(
                {"_id": ObjectId(product_id)},
                {"$set": {
                    "name": form.name.data,
                    "description": form.description.data,
                    "price": float(form.price.data),
                    "image_url": image_url
                }}
            )
            flash('Produk berhasil diperbarui!', 'success')
            return redirect(url_for('manage_products'))
        return render_template('admin/edit_product.html', form=form, product=product)
    except Exception as e:
        flash(f'Error saat mengedit produk: {e}', 'danger')
        return redirect(url_for('manage_products'))

@app.route('/admin/products/delete/<product_id>')
@login_required
def delete_product(product_id):
    try:
        products_collection.delete_one({"_id": ObjectId(product_id)})
        flash('Produk berhasil dihapus!', 'success')
    except Exception as e:
        flash(f'Error saat menghapus produk: {e}', 'danger')
    return redirect(url_for('manage_products'))

# --- Blog Management ---
@app.route('/admin/blog')
@login_required
def manage_blog():
    posts = blog_collection.find().sort("date", -1)
    return render_template('admin/manage_blog.html', posts=posts)

@app.route('/admin/blog/add', methods=['GET', 'POST'])
@login_required
def add_blog_post():
    form = BlogPostForm()
    if form.validate_on_submit():
        image_url = None
        if form.image.data:
            try:
                upload_result = upload(form.image.data, folder="your_website_blog") # Ganti dengan folder Cloudinary Anda
                image_url = upload_result['secure_url']
            except Exception as e:
                flash(f'Gagal mengunggah gambar ke Cloudinary: {e}', 'danger')
                return render_template('admin/add_blog_post.html', form=form)

        new_post = {
            "title": form.title.data,
            "content": form.content.data,
            "author": form.author.data,
            "image_url": image_url,
            "date": datetime.utcnow() # Simpan tanggal posting
        }
        blog_collection.insert_one(new_post)
        flash('Postingan blog berhasil ditambahkan!', 'success')
        return redirect(url_for('manage_blog'))
    return render_template('admin/add_blog_post.html', form=form)

@app.route('/admin/blog/edit/<post_id>', methods=['GET', 'POST'])
@login_required
def edit_blog_post(post_id):
    try:
        post = blog_collection.find_one({"_id": ObjectId(post_id)})
        if not post:
            flash('Postingan blog tidak ditemukan.', 'danger')
            return redirect(url_for('manage_blog'))

        form = BlogPostForm(obj=post)
        if form.validate_on_submit():
            image_url = post.get('image_url')
            if form.image.data:
                try:
                    upload_result = upload(form.image.data, folder="your_website_blog")
                    image_url = upload_result['secure_url']
                except Exception as e:
                    flash(f'Gagal mengunggah gambar ke Cloudinary: {e}', 'danger')
                    return render_template('admin/edit_blog_post.html', form=form, post=post)

            blog_collection.update_one(
                {"_id": ObjectId(post_id)},
                {"$set": {
                    "title": form.title.data,
                    "content": form.content.data,
                    "author": form.author.data,
                    "image_url": image_url,
                    "last_updated": datetime.utcnow() # Update tanggal terakhir diubah
                }}
            )
            flash('Postingan blog berhasil diperbarui!', 'success')
            return redirect(url_for('manage_blog'))
        return render_template('admin/edit_blog_post.html', form=form, post=post)
    except Exception as e:
        flash(f'Error saat mengedit postingan blog: {e}', 'danger')
        return redirect(url_for('manage_blog'))

@app.route('/admin/blog/delete/<post_id>')
@login_required
def delete_blog_post(post_id):
    try:
        blog_collection.delete_one({"_id": ObjectId(post_id)})
        flash('Postingan blog berhasil dihapus!', 'success')
    except Exception as e:
        flash(f'Error saat menghapus postingan blog: {e}', 'danger')
    return redirect(url_for('manage_blog'))

@app.route('/sitemap.xml')
def sitemap():
    base_url = app.config['SITEMAP_BASE_URL']
    urls = []

    # Halaman statis
    urls.append({'loc': url_for('index', _external=True), 'lastmod': datetime.utcnow().isoformat() + 'Z', 'changefreq': 'daily', 'priority': '1.0'})
    urls.append({'loc': url_for('about', _external=True), 'lastmod': datetime.utcnow().isoformat() + 'Z', 'changefreq': 'monthly', 'priority': '0.8'})
    urls.append({'loc': url_for('contact', _external=True), 'lastmod': datetime.utcnow().isoformat() + 'Z', 'changefreq': 'monthly', 'priority': '0.8'})
    urls.append({'loc': url_for('products', _external=True), 'lastmod': datetime.utcnow().isoformat() + 'Z', 'changefreq': 'weekly', 'priority': '0.9'})
    urls.append({'loc': url_for('blog', _external=True), 'lastmod': datetime.utcnow().isoformat() + 'Z', 'changefreq': 'daily', 'priority': '0.9'})

    # Halaman produk individual
    all_products = products_collection.find({}, {"_id": 1}) # Hanya ambil ID
    for product in all_products:
        urls.append({'loc': url_for('product_detail', product_id=str(product['_id']), _external=True), 'lastmod': datetime.utcnow().isoformat() + 'Z', 'changefreq': 'weekly', 'priority': '0.7'})

    # Halaman postingan blog individual
    all_posts = blog_collection.find({}, {"_id": 1, "date": 1}) # Ambil ID dan tanggal
    for post in all_posts:
        lastmod = post.get('last_updated', post.get('date', datetime.utcnow())).isoformat() + 'Z'
        urls.append({'loc': url_for('blog_post', post_id=str(post['_id']), _external=True), 'lastmod': lastmod, 'changefreq': 'daily', 'priority': '0.7'})

    xml_content = render_template('sitemap.xml', urls=urls)
    response = make_response(xml_content)
    response.headers["Content-Type"] = "application/xml"
    return response

@app.route('/robots.txt')
def robots_txt():
    content = """User-agent: *
Allow: /

Sitemap: {}/sitemap.xml
""".format(app.config['SITEMAP_BASE_URL'])
    
    response = make_response(content)
    response.headers["Content-Type"] = "text/plain"
    return response

@app.errorhandler(404)
def not_found_error(error):
    app.logger.warning(f'404 Not Found: {request.url} - {request.remote_addr}')
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    app.logger.error(f'500 Internal Server Error: {request.url} - {request.remote_addr}', exc_info=True)
    return render_template('errors/500.html'), 500

if __name__ == '__main__':
    app.run(debug=False)