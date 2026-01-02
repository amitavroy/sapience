<?php

declare(strict_types=1);

namespace App\Neuron\Nodes;

use App\Models\Audit;
use App\Models\AuditLink;
use App\Neuron\Events\SeoAnalyzeAuditLinksEvent;
use App\Neuron\Events\SeoSearchSimilarWebsiteEvent;
use App\Services\SearchService;
use NeuronAI\Workflow\Node;
use NeuronAI\Workflow\WorkflowState;

class SeoSearchSimilarWebsiteNode extends Node
{
    /**
     * Implement the Node's logic
     */
    public function __invoke(SeoSearchSimilarWebsiteEvent $event, WorkflowState $state): SeoAnalyzeAuditLinksEvent
    {
        logger('Searching for similar websites');

        if (config('sapience.workflow_fake')) {
            logger('Using fake workflow: SeoSearchSimilarWebsiteNode');

            return new SeoAnalyzeAuditLinksEvent;
        }

        $auditId = $state->get('audit_id');
        $audit = Audit::find($auditId);

        if (! $audit) {
            logger('Audit not found', ['audit_id' => $auditId]);

            return new SeoAnalyzeAuditLinksEvent;
        }

        $searchTerms = $audit->search_terms;

        if (empty($searchTerms) || ! is_array($searchTerms)) {
            logger('No search terms found for audit', ['audit_id' => $auditId]);

            return new SeoAnalyzeAuditLinksEvent;
        }

        $searchService = app(SearchService::class);
        $totalCreated = 0;

        collect($searchTerms)->each(function ($searchTerm) use ($searchService, $audit, &$totalCreated): void {
            logger('Searching for term', ['term' => $searchTerm]);

            try {
                $searchResults = $searchService->search($searchTerm);
                $searchResultsArray = $searchResults->toArray();

                logger('Search response received', [
                    'term' => $searchTerm,
                    'response_keys' => array_keys($searchResultsArray),
                    'has_results_key' => isset($searchResultsArray['results']),
                    'results_count' => isset($searchResultsArray['results']) ? count($searchResultsArray['results']) : 0,
                ]);

                // Access results - SearXNG typically returns results in 'results' key
                $results = collect($searchResultsArray['results'] ?? [])->take(5);
                logger('Results extracted', ['term' => $searchTerm, 'count' => $results->count()]);

                if ($results->isEmpty()) {
                    logger('No results found for term', ['term' => $searchTerm]);
                }

                $results->each(function ($result) use ($audit, $searchTerm, &$totalCreated): void {
                    try {
                        AuditLink::create([
                            'audit_id' => $audit->id,
                            'user_id' => $audit->user_id,
                            'url' => $result['url'] ?? '',
                            'title' => $result['title'] ?? null,
                            'content' => $result['content'] ?? null,
                            'search_term' => $searchTerm,
                            'status' => 'pending',
                        ]);
                        $totalCreated++;
                        logger('AuditLink created', ['url' => $result['url'] ?? 'no url']);
                    } catch (\Exception $e) {
                        logger('Error creating AuditLink', [
                            'url' => $result['url'] ?? 'no url',
                            'error' => $e->getMessage(),
                        ]);
                    }
                });
            } catch (\Exception $e) {
                logger('Error searching for term', [
                    'term' => $searchTerm,
                    'error' => $e->getMessage(),
                ]);
            }
        });

        logger('Search results saved', [
            'audit_id' => $auditId,
            'terms_count' => count($searchTerms),
            'links_created' => $totalCreated,
        ]);

        return new SeoAnalyzeAuditLinksEvent;
    }
}
