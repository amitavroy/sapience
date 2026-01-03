<?php

declare(strict_types=1);

namespace App\Neuron\Nodes;

use App\Neuron\Agent\SearchTermAgent;
use App\Neuron\Events\ContextClarificationEvent;
use App\Neuron\Events\SearchEvent;
use NeuronAI\Chat\Messages\UserMessage;
use NeuronAI\Workflow\Node;
use NeuronAI\Workflow\WorkflowState;

class ContextClarificationNode extends Node
{
    /**
     * Implement the Node's logic
     */
    public function __invoke(ContextClarificationEvent $event, WorkflowState $state): SearchEvent
    {
        logger('Context clarification node - checking for user feedback');

        if (config('sapience.workflow_fake')) {
            logger('Using fake workflow: ContextClarificationNode');

            return new SearchEvent;
        }

        $topic = $state->get('topic');
        $searchTerms = $state->get('search_terms', []);

        $feedback = $this->getUserFeedback($topic, $searchTerms);

        $this->processFeedback($feedback, $topic, $searchTerms, $state);

        return new SearchEvent;
    }

    /**
     * Get user feedback, either from interruption or from resume
     */
    private function getUserFeedback(string $topic, array $searchTerms): array
    {
        $feedback = $this->consumeInterruptFeedback();

        if ($feedback === null) {
            return $this->requestInterruption($topic, $searchTerms);
        }

        return $feedback;
    }

    /**
     * Request interruption to get user feedback
     */
    private function requestInterruption(string $topic, array $searchTerms): array
    {
        logger('Interrupting workflow to ask for clarification', [
            'topic' => $topic,
            'search_terms' => $searchTerms,
        ]);

        $interruptionData = $this->interrupt([
            'topic' => $topic,
            'search_terms' => $searchTerms,
            'question' => 'Please review the generated search terms and provide any additional context or clarification to improve the search results.',
            'generated_at' => now()->toIso8601String(),
        ]);

        return $interruptionData;
    }

    /**
     * Process user feedback and update state accordingly
     */
    private function processFeedback(array $feedback, string $topic, array $searchTerms, WorkflowState $state): void
    {
        if ($this->hasAdditionalContext($feedback)) {
            $this->handleAdditionalContext($feedback, $topic, $searchTerms, $state);
        } else {
            logger('No additional context provided, using original search terms', [
                'topic' => $topic,
                'search_terms' => $searchTerms,
                'feedback_keys' => array_keys($feedback),
            ]);
        }

        if ($this->hasRefinedSearchTerms($feedback)) {
            $this->applyRefinedSearchTerms($feedback, $state);
        }
    }

    /**
     * Check if feedback contains additional context
     */
    private function hasAdditionalContext(array $feedback): bool
    {
        return isset($feedback['additional_context']) && ! empty($feedback['additional_context']);
    }

    /**
     * Check if feedback contains refined search terms
     */
    private function hasRefinedSearchTerms(array $feedback): bool
    {
        return isset($feedback['refined_search_terms'])
          && is_array($feedback['refined_search_terms'])
          && ! empty($feedback['refined_search_terms']);
    }

    /**
     * Handle additional context by extracting clarified topic and regenerating search terms
     */
    private function handleAdditionalContext(array $feedback, string $originalTopic, array $originalSearchTerms, WorkflowState $state): void
    {
        $additionalContext = trim($feedback['additional_context']);

        logger('Additional context received, processing clarification', [
            'original_topic' => $originalTopic,
            'additional_context' => $additionalContext,
            'feedback_keys' => array_keys($feedback),
        ]);

        $clarifiedTopic = $this->extractClarifiedTopic($additionalContext);

        $state->set('additional_context', $additionalContext);
        $state->set('topic', $clarifiedTopic);

        $this->regenerateSearchTerms($clarifiedTopic, $originalTopic, $originalSearchTerms, $state);
    }

    /**
     * Extract the clarified topic from user's additional context
     * Handles phrases like "I meant X", "correct to X", "should be X"
     */
    private function extractClarifiedTopic(string $additionalContext): string
    {
        $patterns = [
            '/meant\s+(.+?)(?:\.|$)/i',
            '/correct.*?to\s+(.+?)(?:\.|$)/i',
            '/should be\s+(.+?)(?:\.|$)/i',
        ];

        foreach ($patterns as $pattern) {
            if (preg_match($pattern, $additionalContext, $matches)) {
                return trim($matches[1]);
            }
        }

        return trim($additionalContext);
    }

    /**
     * Regenerate search terms using the clarified topic
     */
    private function regenerateSearchTerms(string $clarifiedTopic, string $originalTopic, array $originalSearchTerms, WorkflowState $state): void
    {
        logger('Regenerating search terms with clarified topic', [
            'original_topic' => $originalTopic,
            'clarified_topic' => $clarifiedTopic,
        ]);

        $searchTermAgent = SearchTermAgent::make();
        $response = $searchTermAgent->chat(new UserMessage($clarifiedTopic));

        $content = $response->getContent();
        $result = json_decode($content, true);

        if (isset($result['alternative_queries']) && is_array($result['alternative_queries'])) {
            $state->set('search_terms', $result['alternative_queries']);

            logger('Search terms regenerated with clarified context', [
                'clarified_topic' => $clarifiedTopic,
                'new_search_terms' => $result['alternative_queries'],
                'old_search_terms' => $originalSearchTerms,
            ]);
        } else {
            logger()->warning('Failed to regenerate search terms, using original terms', [
                'response' => $content,
                'decoded_result' => $result,
            ]);
        }
    }

    /**
     * Apply user-provided refined search terms directly
     */
    private function applyRefinedSearchTerms(array $feedback, WorkflowState $state): void
    {
        $state->set('search_terms', $feedback['refined_search_terms']);
        logger('Search terms refined by user', ['terms' => $feedback['refined_search_terms']]);
    }
}
