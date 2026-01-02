<?php

namespace App\Services;

use App\Models\Dataset;
use App\Models\File;
use DOMDocument;
use DOMXPath;

class UtilService
{
    /**
     * Generate the S3 path for a file in a dataset.
     */
    public static function getFileS3Path(Dataset $dataset, File $file): string
    {
        return "datasets/{$dataset->id}/files/{$file->filename}";
    }

    /**
     * Extract schema types from HTML markup.
     */
    public static function extractSchemaTypes(string $html): string
    {
        if (empty($html)) {
            return 'None detected';
        }

        $dom = new DOMDocument;
        @$dom->loadHTML($html, LIBXML_HTML_NOIMPLIED | LIBXML_HTML_NODEFDTD);
        $xpath = new DOMXPath($dom);

        $schemaTypes = [];
        $scriptTags = $xpath->query('//script[@type="application/ld+json"]');

        foreach ($scriptTags as $script) {
            $jsonContent = trim($script->textContent);
            if (empty($jsonContent)) {
                continue;
            }

            $decoded = json_decode($jsonContent, true);
            if (json_last_error() !== JSON_ERROR_NONE) {
                continue;
            }

            // Handle both single objects and arrays
            $items = is_array($decoded) && array_is_list($decoded) ? $decoded : [$decoded];

            foreach ($items as $item) {
                if (isset($item['@type'])) {
                    $type = $item['@type'];
                    // Remove schema.org namespace if present
                    $type = str_replace('https://schema.org/', '', $type);
                    $type = str_replace('http://schema.org/', '', $type);
                    $schemaTypes[] = $type;
                }
            }
        }

        if (empty($schemaTypes)) {
            return 'None detected';
        }

        return implode(', ', array_unique($schemaTypes));
    }

    /**
     * Format headings array as a hierarchical list.
     */
    public static function formatHeadingsHierarchically(array $headings): string
    {
        if (empty($headings)) {
            return 'No headings detected.';
        }

        // Since we only have text, we'll format them as a simple list
        // In a real implementation, you might want to parse the HTML to get actual h1/h2/h3 hierarchy
        $formatted = '';
        foreach ($headings as $heading) {
            $formatted .= '- '.$heading."\n";
        }

        return trim($formatted);
    }

    /**
     * Truncate content to a maximum character length, ending at word boundary when possible.
     */
    public static function truncateContent(string $content, int $maxChars = 15000): string
    {
        if (mb_strlen($content) <= $maxChars) {
            return $content;
        }

        // Truncate to max chars, but try to end at a word boundary
        $truncated = mb_substr($content, 0, $maxChars);
        $lastSpace = mb_strrpos($truncated, ' ');

        if ($lastSpace !== false && $lastSpace > $maxChars * 0.9) {
            $truncated = mb_substr($truncated, 0, $lastSpace);
        }

        return $truncated."\n\n[Content truncated for analysis...]";
    }
}
