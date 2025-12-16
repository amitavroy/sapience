# Sapience

Sapience is a RAG based application.

# Running the application

To run the application, the best thing to do is run it through Docker.

## Prerequisites

- Docker and Docker Compose installed on your system
- Node.js and npm installed locally (for frontend development)

## Docker Setup

### 1. Environment Configuration

Create a `.env` file in the root directory if it doesn't exist. You can copy from `.env.example` if available, or configure the following environment variables:

**Application:**
- `APP_PORT` - Port for the PHP application (default: 80)
- `UID` - User ID for Docker container (default: 1000)
- `GID` - Group ID for Docker container (default: 1000)

**Database:**
- `DB_DATABASE` - Database name (default: sapience)
- `DB_USERNAME` - Database user (default: sapience)
- `DB_PASSWORD` - Database password (default: sapience)
- `DB_EXTERNAL_PORT` - External MySQL port (default: 3307)
- `DB_ADMIN_UI` - phpMyAdmin port (default: 8081)

**Redis:**
- `REDIS_PORT` - Redis port (default: 6379)

**Mailpit (Email Testing):**
- `MAILPIT_WEBUI` - Mailpit web UI port (default: 8025)
- `MAILPIT_SMTP` - Mailpit SMTP port (default: 1025)
- `MAILPIT_MESSAGES` - Max messages to store (default: 100)

**MinIO (File Storage):**
- `MINIO_API_PORT` - MinIO API port (default: 9000)
- `MINIO_CONSOLE_PORT` - MinIO Console port (default: 9001)
- `MINIO_ROOT_USER` - MinIO root user (default: minioadmin)
- `MINIO_ROOT_PASSWORD` - MinIO root password (default: minioadmin)
- `MINIO_API_CORS_ALLOW_ORIGIN` - CORS allowed origins (default: http://localhost:8000,http://127.0.0.1:8000)

**Typesense (Search):**
- `TYPESENSE_PORT` - Typesense API port (default: 8108)
- `TYPESENSE_API_KEY` - Typesense API key (default: xyz)
- `TYPESENSE_DASHBOARD_PORT` - Typesense Dashboard port (default: 8109)

### 2. Start Docker Services

Start all Docker services:

```bash
docker compose up -d
```

This will start the following services:
- **PHP Application** - Laravel application server
- **Worker** - Queue worker for background jobs
- **MySQL** - MariaDB database
- **phpMyAdmin** - Database administration UI
- **Redis** - Cache and session storage
- **Mailpit** - Email testing tool
- **MinIO** - S3-compatible object storage
- **Typesense** - Search engine
- **Typesense Dashboard** - Typesense administration UI

### 3. Install Dependencies

Install PHP dependencies:

```bash
docker compose exec php composer install
```

Install Node.js dependencies (run locally):

```bash
npm install
```

### 4. Application Setup

Generate application key:

```bash
docker compose exec php php artisan key:generate
```

Run database migrations:

```bash
docker compose exec php php artisan migrate
```

(Optional) Seed the database:

```bash
docker compose exec php php artisan db:seed
```

### 5. Access Services

Once all services are running, you can access:

- **Application**: http://localhost (or the port specified in `APP_PORT`)
- **phpMyAdmin**: http://localhost:8081 (or the port specified in `DB_ADMIN_UI`)
- **Mailpit**: http://localhost:8025 (or the port specified in `MAILPIT_WEBUI`)
- **MinIO Console**: http://localhost:9001 (or the port specified in `MINIO_CONSOLE_PORT`)
- **Typesense Dashboard**: http://localhost:8109 (or the port specified in `TYPESENSE_DASHBOARD_PORT`)

### 6. Frontend Development

**NOTE:** Due to Wayfinder requiring both PHP and Node.js in the same container, you need to run the frontend development server locally:

```bash
npm run dev
```

This will start the Vite development server for hot module replacement.

### 7. Useful Docker Commands

**View running services:**
```bash
docker compose ps
```

**View logs:**
```bash
docker compose logs -f [service-name]
```

**Stop all services:**
```bash
docker compose down
```

**Stop and remove volumes (clean slate):**
```bash
docker compose down -v
```

**Execute commands in PHP container:**
```bash
docker compose exec php [command]
```

**Example - Run Artisan commands:**
```bash
docker compose exec php php artisan [command]
```

**Example - Run tests:**
```bash
docker compose exec php php artisan test
```

**Example - Access PHP shell:**
```bash
docker compose exec php php artisan tinker
```

### 8. Queue Worker

The queue worker runs automatically in the `worker` service. To manually process queues:

```bash
docker compose exec worker php artisan queue:work
```

### 9. Troubleshooting

**Port conflicts:** If you encounter port conflicts, modify the port mappings in `docker-compose.yml` or set different values in your `.env` file.

**Permission issues:** Ensure your `UID` and `GID` in `.env` match your local user ID:
```bash
id -u  # Your UID
id -g  # Your GID
```

**Rebuild containers:** If you make changes to Docker configuration:
```bash
docker compose up -d --build
```

**Clear application cache:**
```bash
docker compose exec php php artisan config:clear
docker compose exec php php artisan cache:clear
docker compose exec php php artisan route:clear
docker compose exec php php artisan view:clear
```

# Application Features

## Organisations

Organisations are the core multi-tenancy feature of Sapience. They allow multiple users to collaborate within isolated workspaces, sharing datasets and conversations while maintaining data separation between different organisations.

### Overview

- **Multi-tenancy**: Each organisation is a separate workspace with its own datasets, conversations, and users
- **User Roles**: Users can have different roles (`admin` or `member`) within each organisation
- **Organisation Isolation**: Datasets and conversations are scoped to organisations, ensuring data privacy
- **Multiple Memberships**: Users can belong to multiple organisations and switch between them

### Key Features

#### Organisation Structure

Each organisation has:
- **UUID**: A unique identifier used for joining organisations via code
- **Name**: The display name of the organisation
- **Users**: Multiple users can belong to an organisation with assigned roles
- **Datasets**: Collections of files and knowledge used for RAG (Retrieval-Augmented Generation)
- **Conversations**: Chat conversations that can be associated with datasets

#### User Roles

- **Admin**: Users who create an organisation automatically become admins. Admins have full control over the organisation.
- **Member**: Users who join an organisation via code become members. Members can access and use organisation resources.

#### Organisation Management

**Creating an Organisation:**
- Users can create a new organisation from the setup screen
- The creator automatically becomes an admin
- The organisation is assigned a unique UUID for sharing

**Joining an Organisation:**
- Users can join an existing organisation using the organisation's UUID code
- New members are assigned the `member` role by default
- Users cannot join the same organisation twice (they'll be redirected to the dashboard if already a member)

**Selecting an Organisation:**
- Users with multiple organisations can select which one to work with
- The selected organisation is stored as `last_organisation_id` for quick access
- Users with only one organisation are automatically redirected to its dashboard

**Organisation Dashboard:**
- Each organisation has its own dashboard showing organisation details and members
- Access is restricted to users who belong to the organisation
- The dashboard displays the organisation's datasets and conversations

### Data Scoping

All major resources in Sapience are scoped to organisations:

- **Datasets**: Belong to a specific organisation and can be accessed by all members
- **Conversations**: Associated with both an organisation and optionally a dataset
- **Files**: Linked to datasets, which are organisation-scoped

This ensures that:
- Data from one organisation is never visible to users from another organisation
- Users can work with multiple organisations without data leakage
- Collaboration happens within the context of a single organisation

### Access Control

The application enforces organisation-based access control:

- **Middleware**: `EnsureUserHasOrganisation` middleware ensures users belong to at least one organisation before accessing protected routes
- **Route Scoping**: Most routes are prefixed with `{organisation}` to ensure context
- **Authorization**: Controllers verify users belong to the organisation before allowing access

### Workflow

1. **First-time Setup**: New users are prompted to either create or join an organisation
2. **Organisation Selection**: Users with multiple organisations select which one to work with
3. **Dashboard Access**: Users access the organisation dashboard to manage datasets and conversations
4. **Context Switching**: Users can switch between organisations by selecting a different one

### Technical Details

**Database Structure:**
- `organisations` table stores organisation data with UUID and name
- `organisation_user` pivot table manages many-to-many relationship with roles
- `users.last_organisation_id` tracks the user's current organisation context

**Model Relationships:**
- `Organisation` has many `users` (many-to-many with roles)
- `Organisation` has many `datasets`
- `Organisation` has many `conversations`
- `User` belongs to many `organisations` (many-to-many with roles)
- `Dataset` belongs to an `organisation`
- `Conversation` belongs to an `organisation`

## Datasets

Datasets are the core knowledge containers in Sapience's RAG (Retrieval-Augmented Generation) system. They organize files and documents that serve as the knowledge base for AI-powered conversations, enabling context-aware responses based on uploaded content.

### Overview

- **Knowledge Base**: Datasets contain collections of files (PDFs, documents, etc.) that are processed and indexed for semantic search
- **RAG Integration**: Each dataset powers conversations by providing relevant context from its files
- **Organisation Scoped**: Datasets belong to organisations, ensuring data isolation and collaboration within teams
- **Customizable AI Behavior**: Datasets include custom instructions that control how the AI interprets and responds to queries

### Key Features

#### Dataset Structure

Each dataset includes:
- **UUID**: Unique identifier for the dataset
- **Name & Description**: Human-readable identification and purpose
- **Instructions**: Custom background/system instructions that define the AI's role and knowledge scope
- **Output Instructions**: Guidelines for how the AI should format and structure its responses
- **Active Status**: Toggle to enable/disable the dataset for conversations
- **Owner**: The user who created the dataset (admins only)
- **Organisation**: The organisation the dataset belongs to

#### File Management

- **File Upload**: Multiple files can be uploaded to a dataset
- **File Processing**: Files are asynchronously processed and indexed into a vector store
- **Supported Formats**: PDFs and other document formats (extensible via FileDataLoader)
- **File Status Tracking**: Files have statuses (pending, processing, completed, failed) to track processing state
- **Storage**: Files are stored in S3-compatible storage (MinIO in development, AWS S3 in production)

#### Vector Store Integration

- **Typesense Collection**: Each dataset gets its own Typesense collection for vector search
- **Document Chunking**: Files are automatically chunked into smaller documents for better retrieval
- **Embeddings**: Documents are converted to vector embeddings using OpenAI's embedding model
- **Metadata Enrichment**: Each document chunk includes file metadata (file ID, UUID, filename, mime type, chunk index)

#### RAG (Retrieval-Augmented Generation)

- **Context Retrieval**: When users ask questions, relevant document chunks are retrieved from the dataset's vector store
- **Custom Instructions**: Dataset instructions are used as system prompts to guide AI behavior
- **Semantic Search**: Vector similarity search finds the most relevant content for each query
- **Conversation Context**: Conversations can be associated with specific datasets to scope knowledge retrieval

### Dataset Management

**Creating a Dataset:**
- Only organisation admins can create datasets
- Requires a name and optional description
- A Typesense collection is automatically created for the dataset
- The creator becomes the dataset owner

**Editing a Dataset:**
- Only organisation admins can edit datasets
- Can update name, description, instructions, and output instructions
- Can toggle active status to enable/disable the dataset

**Viewing a Dataset:**
- All organisation members can view datasets
- Shows dataset details, associated files, and file counts
- Displays processing status of uploaded files

**File Upload Process:**
1. User requests a file upload (gets signed URL for direct S3 upload)
2. File is uploaded to S3/MinIO storage
3. File record is created and associated with the dataset
4. `ProcessFileForVectorStore` job is queued for asynchronous processing
5. File is downloaded, chunked, embedded, and indexed into Typesense
6. File status is updated to reflect processing completion or failure

### Dataset Instructions

Datasets support two types of custom instructions:

**Background Instructions (`instructions`):**
- Define the AI's role and knowledge scope
- Specify how the AI should interpret the documents
- Default: "You are a helpful assistant that can answer questions about the documents in the vector store."

**Output Instructions (`output_instructions`):**
- Control response format and style
- Define language preferences and structure
- Default: Instructions for concise answers, same language as question, and follow-up suggestions

These instructions are combined into a system prompt that guides the AI's behavior in conversations using this dataset.

### Access Control

- **Organisation Scoped**: Datasets are only accessible to members of the owning organisation
- **Admin Only**: Only organisation admins can create and edit datasets
- **Member Access**: All organisation members can view datasets and use them in conversations
- **Route Protection**: Controllers verify organisation membership and admin status before allowing operations

### Workflow

1. **Dataset Creation**: Admin creates a dataset within an organisation
2. **File Upload**: Files are uploaded to the dataset
3. **Processing**: Files are automatically processed and indexed into the vector store
4. **Conversation**: Users create conversations associated with the dataset
5. **Query**: Users ask questions, and the AI retrieves relevant context from the dataset's files
6. **Response**: AI generates responses based on retrieved context and dataset instructions

### Technical Details

**Database Structure:**
- `datasets` table stores dataset metadata (name, description, instructions, owner, organisation)
- `dataset_file` pivot table manages many-to-many relationship between datasets and files
- `files` table stores file metadata (filename, size, mime type, status)

**Vector Store:**
- Each dataset has a dedicated Typesense collection
- Collection naming: `org_{organisation_id}_dataset_{dataset_id}`
- Documents are stored with embeddings and metadata
- Vector dimension matches OpenAI embedding model (typically 1536)

**File Processing Pipeline:**
- Files are stored in S3/MinIO with path: `organisations/{organisation_id}/datasets/{dataset_id}/files/{file_uuid}/{filename}`
- Processing happens asynchronously via Laravel queues
- FileDataLoader handles different file formats (PDF via PdfReader)
- Documents are enriched with file metadata before indexing
- Processing time is benchmarked and logged

**Model Relationships:**
- `Dataset` belongs to an `organisation`
- `Dataset` belongs to an `owner` (User)
- `Dataset` has many `files` (many-to-many)
- `Dataset` has many `conversations`
- `File` belongs to many `datasets` (many-to-many)
- `Conversation` belongs to a `dataset` (optional)

**RAG Implementation:**
- `SapienceBot` extends `RAG` class from NeuronAI
- Uses OpenAI for both chat and embeddings
- Vector store is Typesense-based
- Chat history is stored in Eloquent (Message model)
- System prompt is dynamically generated from dataset instructions

