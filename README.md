# LaTeX2image

[![Build Status](https://travis-ci.org/dzhuang/latex2image.svg?branch=master)](https://travis-ci.org/dzhuang/latex2image)
[![codecov](https://codecov.io/gh/dzhuang/latex2image/branch/master/graph/badge.svg)](https://codecov.io/gh/dzhuang/latex2image)

### Dockerized Service from LaTex code to image

Convert LaTex code to images using a dockerized service.

## Install
    
    docker pull dzhuang/latex2image:latest

    git clone https://github.com/dzhuang/latex2image.git
    cd latex2image

    cp docker-compose-example.yml docker-compose.yml
    vi docker-compose.yml # Change your configurations

    docker-compose up -d

## Usage
In your browser, navigate to http://127.0.0.1:8020/, and login with the superuser name you configured in the 
`docker-compose.yml` (see below).

The APIs are available:
- `api/list`: List all converted objects, `GET`, `POST`(create new), `PUT`(update) and `DELETE` are allowed. `POST`
  requests need the following post data:
  - `tex_source`: string, required.
  - `image_format`: string, required. Allowed format include `png` and `svg`, when `png` will return a png image with 
  resolution 96.
  - `compiler`: string, required. Allowed compiler include `latex`, `pdflatex`, `xelatex` and `lualatex`. Notice that
  when `compiler` is `latex` while the source code contains `tikz` pictures, it will return `svg` images disregarding 
  the `image_format` param.
  - `tex_key`: Optional, see below.
- `api/create`: Only `POST` requests are allowed.
- `api/detail/<tex_key>`: Getting information of the converted result with `tex_key`.

Notice:
- `tex_key`s are auto generated if not provided when `create`. It can be thought of as the query key, when the `tex_key`
 exists in the database, it will return the saved item (as well as compile error raised) instead of doing the convert.
- No LaTex source code will be saved in the database.
- Make sure your tex code will compile to only one pdf page, or it will raise errors.

## Configurations

The following short-handed settings items can be configured in your `docker-compose.yml` file.

| Django Settings/Environment Variable | Detail                               |
|--------------------------------------|--------------------------------------|
| L2I_ALLOWED_HOST_*                  | A host which is to be appended to `settings.ALLOWED_HOSTS` |
| L2I_MONGODB_HOST                   | The host name of the mongodb used      |
| L2I_MONGODB_USERNAME                 | The username of mongodb used   |
| L2I_MONGODB_PASSWORD                 | The passwd of mongodb used   |
| L2I_CORS_ORIGIN_WHITELIST_*          | The allowed hosts which will not be checked by CSRF requests. (Notice, need to add `http:\\` or `https:\\` as prefix.) |
| L2I_LANGUAGE_CODE                  | Language code used (i18n is in developmenet)              |
| L2I_TZ                     | Timezone used.|
| L2I_DEBUG                  | For settings.DEBUG. Allowed values [`off`, `on`], default to `off`. | 
| L2I_API_CACHE_FIELD | A field name which is supposed to be cached since the 1st request when using create and detail api with a `field` querystring. Either `image` (the url of the image) or `latex_url`. Notice that compile error will always be cached. If changed in production server, a flush of cache will be needed.|
| L2I_CACHE_MAX_BYTES | The maximum size above which the attribute won't be cached. |
| L2I_KEY_VERSION | A string appended to the auto generated `tex_key`, which is used as the identifier of the Tex source code. Default to 1. |
| DJANGO_SUPERUSER_USERNAME | Superuser name created for the first run. String, no quote. |
| DJANGO_SUPERUSER_PASSWORD | Superuser password created for the first run. String, no quote. |

### Advanced Configurations

You can map the folder `latex2image/local_settings` to your local machine in the `voluems` block, and write a file named `local_settings.py` in it
to override all setting items (including those set in the `docker-compose.yml` file).

### Extra packages

If you need to install more Python packages, you can map the folder `latex2image/local_settings` to a local folder, and
put a `requirements.txt` in it.

## Contribute to the project
Contributions to the project are welcome.

    git clone https://github.com/dzhuang/latex2image.git
    cd latex2image/latex2image

    # Create virtualenv
    python -m virtualenv .env
    source .env/bin/activate

    pip install -r requirements.txt
    
    # Do your development...
    
    # Install test dependancies
    pip install factory_boy
    pip install coverage
    coverage run manage.py test tests


## Customized build
If you want to add other fonts to the image, you need to provide a downloadable url of a `tar.gz` file, and set it in Travis-CI options with name `MY_EXTRA_FONTS_GZ`. 

### ALERT 
To include fonts in your own builds, You must respect the intellectual property rights (LICENSE) of those fonts, and take the correspond legal responsibility.
