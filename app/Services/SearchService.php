<?php

namespace App\Services;

use Illuminate\Http\Client\Response;
use Illuminate\Support\Collection;
use Illuminate\Support\Facades\Http;

class SearchService
{
    /**
     * Perform a search query.
     */
    public function search(string $query): Collection
    {
        /** @var Response $response */
        $response = Http::baseUrl(config('services.search.host'))
            ->get('/search', [
                'q' => $query,
                'format' => 'json',
            ]);

        if (! $response->successful()) {
            logger('Search service request failed', [
                'status' => $response->status(),
                'body' => $response->body(),
                'query' => $query,
            ]);

            return collect([]);
        }

        return $response->collect();
    }
}
