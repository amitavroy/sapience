############################################
# Base Image
############################################
FROM serversideup/php:8.4-fpm-nginx-bookworm AS base

############################################
# Development Image
############################################
FROM base AS development

ENV PHP_OPCACHE_ENABLE=1

# Switch to root so we can do root things
USER root

# Install Poppler utilities and Node.js
RUN apt-get update && \
    apt-get install -y --no-install-recommends poppler-utils && \
    curl -fsSL https://deb.nodesource.com/setup_lts.x | bash - && \
    apt-get install -y nodejs && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Adding packages for Code coverage
RUN install-php-extensions pcov opentelemetry

# Save the build arguments as a variable
ARG USER_ID
ARG GROUP_ID

# Use the build arguments to change the UID
# and GID of www-data while also changing
# the file permissions for NGINX
RUN docker-php-serversideup-set-id www-data $USER_ID:$GROUP_ID && \
    \
    # Update the file permissions for our NGINX service to match the new UID/GID
    docker-php-serversideup-set-file-permissions --owner $USER_ID:$GROUP_ID --service nginx

WORKDIR /var/www/html

# Copy our app files as www-data (33:33)
COPY --chown=www-data:www-data . /var/www/html

# Drop back to our unprivileged user
USER www-data

############################################
# Production Image
############################################

# Since we're calling "base", production isn't
# calling any of that permission stuff
FROM base AS production

ENV PHP_OPCACHE_ENABLE=1

USER root

# Install Poppler utilities and Node.js
RUN apt-get update && \
    apt-get install -y --no-install-recommends poppler-utils && \
    curl -fsSL https://deb.nodesource.com/setup_lts.x | bash - && \
    apt-get install -y nodejs && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN install-php-extensions pcov opentelemetry

WORKDIR /var/www/html

COPY composer.* ./

RUN composer install

COPY package.json package-lock.json ./

RUN npm install

# Copy our app files as www-data (33:33)
COPY --chown=www-data:www-data . /var/www/html

# Drop back to our unprivileged user
USER www-data
