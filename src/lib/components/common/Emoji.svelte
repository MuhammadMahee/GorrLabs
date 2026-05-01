<script lang="ts">
	import { shortCodesToEmojis } from '$lib/stores';

	export let shortCode: string;
	export let className = 'size-4';

	const emojiFromCodepoints = (codepoints: string) =>
		codepoints
			.split('-')
			.map((codepoint) => String.fromCodePoint(Number.parseInt(codepoint, 16)))
			.join('');
</script>

{#if $shortCodesToEmojis[shortCode]}
	<span aria-label={shortCode} class={className}>{emojiFromCodepoints($shortCodesToEmojis[shortCode])}</span>
{:else}
	<span class={className}>{shortCode}</span>
{/if}
