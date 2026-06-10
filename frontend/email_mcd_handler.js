function bindEmailMCDButtons(container) {
    container.querySelectorAll('.email-mcd-btn').forEach(btn => {
        btn.addEventListener('click', async (e) => {
            e.stopPropagation();
            const constId = btn.dataset.constituency;
            const summary = btn.dataset.summary || '';

            try {
                const [mcdRes, issueRes] = await Promise.all([
                    fetch(`${API}/api/mcd-email?constituency_id=${constId}`),
                    fetch(`${API}/api/issues?constituency_id=${constId}&limit=1`),
                ]);
                const mcdData = await mcdRes.json();

                const to = mcdData.mcd_email || '';
                const cc = mcdData.mla_email || '';
                const subject = encodeURIComponent(`Civic Complaint: ${summary.substring(0, 80)}`);
                let body = `To the Municipal Corporation of Delhi,\n\n`;
                body += `I wish to report the following civic issue:\n\n`;
                body += `"${summary}"\n\n`;
                body += `Location: ${mcdData.mcd_zone || 'Delhi'} zone, Constituency: ${constId}\n`;
                body += `\n\n---\nSent via Delhi Civic Watch\n`;
                if (cc) body += `\nMLA ${mcdData.mla_name || ''} in CC`;

                window.location.href = `mailto:${to}?cc=${cc}&subject=${subject}&body=${encodeURIComponent(body)}`;
            } catch {
                showToast('Could not load MCD email');
            }
        });
    });
}
