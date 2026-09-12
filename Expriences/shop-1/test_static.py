from shop.app import app
print('static_folder:', app.static_folder)
print('static_url_path:', app.static_url_path)
import os
print('exists:', os.path.exists(app.static_folder))
print('files:', os.listdir(app.static_folder))
