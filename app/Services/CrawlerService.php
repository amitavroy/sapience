<?php

namespace App\Services;

use App\Data\CrawlerResultData;
use DOMDocument;
use DOMElement;
use DOMXPath;
use GuzzleHttp\Client;

class CrawlerService
{
    private Client $client;

    public function __construct()
    {
        $this->client = new Client([
            'timeout' => 30,
            'verify' => true,
            'allow_redirects' => true,
            'headers' => [
                'User-Agent' => $this->getUserAgent(),
                'Accept' => 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language' => 'en-US,en;q=0.5',
                'Accept-Encoding' => 'gzip, deflate, br',
                'Connection' => 'keep-alive',
                'Upgrade-Insecure-Requests' => '1',
            ],
        ]);
    }

    public function execute(string $url): CrawlerResultData
    {
        try {
            $html = $this->fetchHtml($url);

            return new CrawlerResultData(
                success: true,
                markup: $this->extractMarkup($html),
                meta: $this->extractMetaFields($html),
                title: $this->extractPageTitle($html),
                headings: $this->extractHeadings($html),
                content: $this->extractPureText($html),
            );
        } catch (\Exception $e) {
            return new CrawlerResultData(
                success: false,
                markup: '',
                meta: [],
                title: '',
                headings: [],
                content: '',
            );
        }
    }

    private function fetchHtml(string $url): string
    {
        $response = $this->client->get($url);

        return $response->getBody()->getContents();
    }

    private function extractMarkup(string $html): string
    {
        return $html;
    }

    private function extractMetaFields(string $html): array
    {
        $dom = new DOMDocument;
        @$dom->loadHTML($html, LIBXML_HTML_NOIMPLIED | LIBXML_HTML_NODEFDTD);
        $xpath = new DOMXPath($dom);

        $meta = [];

        // Extract standard meta tags
        $metaTags = $xpath->query('//meta[@name or @property]');
        foreach ($metaTags as $tag) {
            if (! ($tag instanceof DOMElement)) {
                continue;
            }

            $name = $tag->getAttribute('name') ?: $tag->getAttribute('property');
            $content = $tag->getAttribute('content');

            if ($name && $content) {
                $meta[$name] = $content;
            }
        }

        // Extract Open Graph tags (og:*)
        $ogTags = $xpath->query('//meta[@property]');
        foreach ($ogTags as $tag) {
            if (! ($tag instanceof DOMElement)) {
                continue;
            }

            $property = $tag->getAttribute('property');
            $content = $tag->getAttribute('content');

            if ($property && $content) {
                $meta[$property] = $content;
            }
        }

        // Extract Twitter Card tags (twitter:*)
        $twitterTags = $xpath->query('//meta[@name[starts-with(., "twitter:")]]');
        foreach ($twitterTags as $tag) {
            if (! ($tag instanceof DOMElement)) {
                continue;
            }

            $name = $tag->getAttribute('name');
            $content = $tag->getAttribute('content');

            if ($name && $content) {
                $meta[$name] = $content;
            }
        }

        return $meta;
    }

    private function extractPageTitle(string $html): string
    {
        $dom = new DOMDocument;
        @$dom->loadHTML($html, LIBXML_HTML_NOIMPLIED | LIBXML_HTML_NODEFDTD);
        $xpath = new DOMXPath($dom);

        $titleNodes = $xpath->query('//title');
        if ($titleNodes->length > 0) {
            return trim($titleNodes->item(0)->textContent);
        }

        return '';
    }

    private function extractHeadings(string $html): array
    {
        $dom = new DOMDocument;
        @$dom->loadHTML($html, LIBXML_HTML_NOIMPLIED | LIBXML_HTML_NODEFDTD);
        $xpath = new DOMXPath($dom);

        $headings = [];
        $headingTags = $xpath->query('//h1 | //h2 | //h3');

        foreach ($headingTags as $heading) {
            $text = trim($heading->textContent);
            if (! empty($text)) {
                $headings[] = $text;
            }
        }

        return $headings;
    }

    private function extractPureText(string $html): string
    {
        // Remove HTML comments first
        $html = preg_replace('/<!--.*?-->/s', '', $html);

        $dom = new DOMDocument;
        @$dom->loadHTML('<?xml encoding="UTF-8">'.$html, LIBXML_HTML_NOIMPLIED | LIBXML_HTML_NODEFDTD);

        $xpath = new DOMXPath($dom);

        // Remove script elements
        $scripts = $xpath->query('//script');
        foreach ($scripts as $script) {
            $script->parentNode?->removeChild($script);
        }

        // Remove style elements
        $styles = $xpath->query('//style');
        foreach ($styles as $style) {
            $style->parentNode?->removeChild($style);
        }

        // Remove noscript elements
        $noscripts = $xpath->query('//noscript');
        foreach ($noscripts as $noscript) {
            $noscript->parentNode?->removeChild($noscript);
        }

        // Remove SVG elements (often contain junk)
        $svgs = $xpath->query('//svg');
        foreach ($svgs as $svg) {
            $svg->parentNode?->removeChild($svg);
        }

        // Remove all inline style attributes
        $elementsWithStyle = $xpath->query('//*[@style]');
        foreach ($elementsWithStyle as $element) {
            if ($element instanceof DOMElement) {
                $element->removeAttribute('style');
            }
        }

        // Remove JavaScript event handlers (onclick, onerror, etc.)
        $eventAttributes = ['onclick', 'onerror', 'onload', 'onmouseover', 'onmouseout', 'onfocus', 'onblur', 'onchange', 'onsubmit'];
        foreach ($eventAttributes as $attr) {
            $elements = $xpath->query("//*[@{$attr}]");
            foreach ($elements as $element) {
                if ($element instanceof DOMElement) {
                    $element->removeAttribute($attr);
                }
            }
        }

        // Remove data attributes that might contain JavaScript/JSON
        $dataAttributes = $xpath->query('//*[starts-with(name(@*), "data-")]');
        foreach ($dataAttributes as $element) {
            if ($element instanceof DOMElement) {
                $attributes = $element->attributes;
                $toRemove = [];
                foreach ($attributes as $attr) {
                    if ($attr instanceof \DOMAttr && str_starts_with($attr->name, 'data-')) {
                        $toRemove[] = $attr->name;
                    }
                }
                foreach ($toRemove as $attrName) {
                    $element->removeAttribute($attrName);
                }
            }
        }

        // Remove common non-content elements
        $nonContentSelectors = [
            '//nav',
            '//header',
            '//footer',
            '//aside',
            '//iframe',
            '//object',
            '//embed',
            '//applet',
            '//canvas',
            '//audio',
            '//video',
        ];

        foreach ($nonContentSelectors as $selector) {
            $elements = $xpath->query($selector);
            foreach ($elements as $element) {
                $element->parentNode?->removeChild($element);
            }
        }

        // Extract content preserving headings in order
        $body = $xpath->query('//body');
        if ($body->length === 0) {
            return '';
        }

        $contentParts = [];
        $bodyElement = $body->item(0);

        // Recursively extract text content preserving heading structure
        $this->extractTextWithHeadings($bodyElement, $contentParts);

        // Join all parts
        $text = implode(' ', $contentParts);

        // Clean up the text
        // Remove excessive whitespace
        $text = preg_replace('/\s+/', ' ', $text);
        // Remove lines that are just whitespace or very short (likely junk)
        $lines = explode(' ', $text);
        $lines = array_filter($lines, function ($line) {
            $trimmed = trim($line);

            // Keep lines that are meaningful (more than 3 chars or contain actual words)
            return strlen($trimmed) > 3 || preg_match('/\b\w{2,}\b/', $trimmed);
        });
        $text = implode(' ', $lines);

        // Final cleanup
        $text = preg_replace('/\s+/', ' ', $text);
        $text = trim($text);

        return $text;
    }

    /**
     * Recursively extract text content while preserving headings
     */
    private function extractTextWithHeadings(\DOMNode $node, array &$contentParts): void
    {
        if ($node->nodeType === XML_TEXT_NODE) {
            $text = trim($node->textContent);
            if (! empty($text)) {
                $contentParts[] = $text;
            }

            return;
        }

        if ($node->nodeType === XML_ELEMENT_NODE) {
            $tagName = strtolower($node->nodeName);

            // Check if it's a heading - extract its full text content and skip children
            if (preg_match('/^h[1-6]$/', $tagName)) {
                $headingText = trim($node->textContent);
                if (! empty($headingText)) {
                    $contentParts[] = $headingText;
                }

                return; // Don't process children of headings to avoid duplication
            }

            // For other elements, recursively process children
            foreach ($node->childNodes as $child) {
                $this->extractTextWithHeadings($child, $contentParts);
            }
        } else {
            // For other node types, process children
            foreach ($node->childNodes as $child) {
                $this->extractTextWithHeadings($child, $contentParts);
            }
        }
    }

    private function getUserAgent(): string
    {
        $userAgents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
        ];

        return $userAgents[array_rand($userAgents)];
    }
}
