<?php

declare(strict_types=1);

namespace App\Neuron\Agent;

use App\Neuron\Dto\ContentAnalysisOutput;
use NeuronAI\Agent;
use NeuronAI\Chat\Messages\UserMessage;
use NeuronAI\Providers\AIProviderInterface;
use NeuronAI\Providers\OpenAI\OpenAI;
use NeuronAI\SystemPrompt;

class ContentAnalysisSummariserAgent extends Agent
{
    protected function provider(): AIProviderInterface
    {
        return new OpenAI(
            key: config('services.openai.key'),
            model: config('services.openai.chat_model'),
        );
    }

    public function instructions(): string
    {
        return (string) new SystemPrompt(
            background: [
                'You are an SEO and content analysis expert specializing in creating comprehensive markdown reports.',
                'You will receive a structured content analysis with multiple sections and data points.',
                'Your task is to create a well-formatted markdown report that captures ALL keys and values from the analysis.',
                'The report should be professional, comprehensive, and easy to read.',
                'Include all analysis points: Classification, Topic Analysis, Content Assessment, SEO Assessment, and Competitor Search Strategy.',
                'Format arrays as bulleted lists, use proper markdown headings, and ensure every key-value pair is included.',
            ],
        );
    }

    public function summarize(ContentAnalysisOutput $contentAnalysis): string
    {
        $prompt = $this->buildPrompt($contentAnalysis);

        $response = $this->chat(new UserMessage($prompt));

        return $response->getContent();
    }

    private function buildPrompt(ContentAnalysisOutput $contentAnalysis): string
    {
        $uniqueAngle = $contentAnalysis->unique_angle ?? 'None identified';
        $secondaryKeywords = $this->formatArray($contentAnalysis->secondary_keywords);
        $entities = $this->formatArray($contentAnalysis->entities);
        $questionsAddressed = $this->formatArray($contentAnalysis->questions_addressed);
        $contentStrengths = $this->formatArray($contentAnalysis->content_strengths);
        $contentWeaknesses = $this->formatArray($contentAnalysis->content_weaknesses);
        $titleTagIssues = $this->formatArray($contentAnalysis->title_tag_issues);
        $metaDescriptionIssues = $this->formatArray($contentAnalysis->meta_description_issues);
        $headingIssues = $this->formatArray($contentAnalysis->heading_issues);
        $schemaOpportunities = $this->formatArray($contentAnalysis->schema_opportunities);
        $searchQueries = $this->formatArray($contentAnalysis->search_queries);
        $competitorMustHave = $this->formatArray($contentAnalysis->competitor_must_have);
        $competitorGoodSignals = $this->formatArray($contentAnalysis->competitor_good_signals);
        $competitorExcludeSignals = $this->formatArray($contentAnalysis->competitor_exclude_signals);
        $comparisonDimensions = $this->formatArray($contentAnalysis->comparison_dimensions);

        return <<<PROMPT
You are an SEO and content analysis expert. Create a comprehensive markdown report based on the following content analysis data.

## Content Analysis Data

### Classification
- **Content Type:** {$contentAnalysis->content_type}
- **Search Intent:** {$contentAnalysis->search_intent}
- **Industry Vertical:** {$contentAnalysis->industry_vertical}
- **Target Audience:** {$contentAnalysis->target_audience}

### Topic Analysis
- **Primary Topic:** {$contentAnalysis->primary_topic}
- **Primary Keyword:** {$contentAnalysis->primary_keyword}
- **Secondary Keywords:** {$secondaryKeywords}
- **Entities:** {$entities}
- **Questions Addressed:** {$questionsAddressed}

### Content Assessment
- **Content Depth:** {$contentAnalysis->content_depth}
- **Content Strengths:** {$contentStrengths}
- **Content Weaknesses:** {$contentWeaknesses}
- **Unique Angle:** {$uniqueAngle}

### SEO Assessment
- **Title Tag Quality:** {$contentAnalysis->title_tag_quality}
- **Title Tag Issues:** {$titleTagIssues}
- **Meta Description Quality:** {$contentAnalysis->meta_description_quality}
- **Meta Description Issues:** {$metaDescriptionIssues}
- **Heading Structure Quality:** {$contentAnalysis->heading_structure_quality}
- **Heading Issues:** {$headingIssues}
- **Schema Opportunities:** {$schemaOpportunities}

### Competitor Search Strategy
- **Search Queries:** {$searchQueries}
- **Competitor Must Have:** {$competitorMustHave}
- **Competitor Good Signals:** {$competitorGoodSignals}
- **Competitor Exclude Signals:** {$competitorExcludeSignals}
- **Comparison Dimensions:** {$comparisonDimensions}

---

## Your Task

Create a comprehensive markdown report that:

1. **Captures ALL keys and values** from the analysis above
2. **Organizes the information** into clear sections with proper markdown headings
3. **Formats arrays** as bulleted lists or numbered lists where appropriate
4. **Provides context** and explanations where helpful
5. **Uses proper markdown formatting** (headings, lists, emphasis, etc.)

The report should be professional, comprehensive, and serve as a complete summary of the content analysis. Every key-value pair must be included in the final report.
PROMPT;
    }

    private function formatArray(array $items): string
    {
        if (empty($items)) {
            return 'None';
        }

        return implode(', ', array_map(fn ($item) => is_string($item) ? $item : json_encode($item), $items));
    }
}
