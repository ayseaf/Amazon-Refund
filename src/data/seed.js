const SEEDED_AT = '2026-01-01T00:00:00.000Z';

/**
 * First-run library. These rows are ordinary data: deleting them sticks.
 */
function createSeed() {
  const groups = [
    { id: 'group-video-editing', name: 'Video Editing', icon: '🎬' },
    { id: 'group-ai-tools', name: 'AI Tools', icon: '✨' },
    { id: 'group-marketing', name: 'Marketing', icon: '📣' },
  ].map((group, order) => ({
    ...group,
    order,
    createdAt: SEEDED_AT,
    updatedAt: SEEDED_AT,
  }));

  const pages = [
    ['page-youtube', 'group-video-editing', 'YouTube', 'https://www.youtube.com/'],
    ['page-vimeo', 'group-video-editing', 'Vimeo', 'https://vimeo.com/'],
    ['page-chatgpt', 'group-ai-tools', 'ChatGPT', 'https://chatgpt.com/'],
    ['page-claude', 'group-ai-tools', 'Claude', 'https://claude.ai/'],
    ['page-instagram', 'group-marketing', 'Instagram', 'https://www.instagram.com/'],
    ['page-mailchimp', 'group-marketing', 'Mailchimp', 'https://mailchimp.com/'],
  ].map(([id, groupId, name, url], index) => ({
    id,
    groupId,
    name,
    url,
    order: index % 2,
    createdAt: SEEDED_AT,
    updatedAt: SEEDED_AT,
    thumbnailCapturedAt: null,
    faviconMime: null,
  }));

  return {
    version: 1,
    selectedGroupId: groups[0].id,
    groups,
    pages,
  };
}

module.exports = { createSeed, SEEDED_AT };
