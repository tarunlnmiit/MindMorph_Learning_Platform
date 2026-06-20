# MERN Stack — Curated Notes

The MERN stack is a JavaScript stack for building full-stack web applications. MERN stands for
MongoDB, Express, React, and Node.js. All four layers use JavaScript (or TypeScript), so a single
language spans the database access layer, the API server, and the browser UI.

## The four layers

- **MongoDB** — a document database that stores data as flexible, JSON-like BSON documents. It pairs
  naturally with JavaScript objects and is accessed from Node with the official driver or Mongoose ODM.
- **Express** — a minimal, unopinionated HTTP framework for Node.js. It defines routes, middleware,
  and request/response handling for the REST or GraphQL API.
- **React** — a component-based library for building the client UI. It renders the single-page app and
  talks to the Express API over HTTP (commonly with fetch, axios, or TanStack Query).
- **Node.js** — the server-side JavaScript runtime that hosts Express and runs the backend logic.

## How a request flows

A React component triggers an HTTP request to an Express route. Express middleware authenticates and
validates the request, queries MongoDB through Mongoose, and returns JSON. React stores the response in
state and re-renders. Authentication is typically token-based (JWT) with tokens stored client-side and
verified by Express middleware on each protected route.

## Common deployment

The React app is built to static assets and served from a CDN or the Express server. The Node/Express
API runs as a long-lived process (often behind a process manager like PM2 or in a container), and
MongoDB is hosted on a managed service such as MongoDB Atlas. Environment variables hold secrets like
the database connection string and JWT signing key.
