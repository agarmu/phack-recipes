\getenv cms_password POSTGRES_PASSWORD
CREATE ROLE cms WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION PASSWORD :'cms_password';
CREATE DATABASE cms OWNER cms;
-- Administration is done by socket so don't need TCP login to be allowed
ALTER ROLE postgres PASSWORD NULL;
