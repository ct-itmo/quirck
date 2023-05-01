FROM ghcr.io/soluto/oidc-server-mock

COPY clients.json /clients.json
COPY identity.json /identity.json
COPY server.json /server.json
COPY users.json /users.json

ENV ASPNETCORE_ENVIRONMENT Development
ENV CLIENTS_CONFIGURATION_PATH /clients.json
ENV IDENTITY_RESOURCES_PATH /identity.json
ENV SERVER_OPTIONS_PATH /server.json
ENV USERS_CONFIGURATION_PATH /users.json
ENV LOGIN_OPTIONS_INLINE {"AllowRememberLogin": false}
ENV LOGOUT_OPTIONS_INLINE {"AutomaticRedirectAfterSignOut": true}
ENV OVERRIDE_STANDARD_IDENTITY_RESOURCES True
