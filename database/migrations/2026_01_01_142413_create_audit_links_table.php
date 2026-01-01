<?php

use App\Models\Audit;
use App\Models\User;
use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    /**
     * Run the migrations.
     */
    public function up(): void
    {
        Schema::create('audit_links', function (Blueprint $table) {
            $table->id();
            $table->foreignIdFor(Audit::class)->index();
            $table->foreignIdFor(User::class)->index();
            $table->string('url');
            $table->string('title')->nullable();
            $table->text('content')->nullable();
            $table->longText('summary')->nullable();
            $table->string('search_term');
            $table->string('status')->default('pending');
            $table->timestamps();
        });
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        Schema::dropIfExists('audit_links');
    }
};
