import nodemailer from 'nodemailer';

export const prerender = false;

const RECIPIENTS = new Set([
  'info@afaitaca.org',
  'menjador@afaitaca.org',
  'acollida@afaitaca.org',
  'extraescolars@afaitaca.org',
  'formacio@afaitaca.org',
  'mediambient@afaitaca.org',
  'patis@afaitaca.org',
  'festes@afaitaca.org',
  'casal@afaitaca.org',
  'comunicacio@afaitaca.org',
]);

const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

const json = (body, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: {
      'Content-Type': 'application/json',
    },
  });

const getString = (value) => (typeof value === 'string' ? value.trim() : '');

const stripHeaderLineBreaks = (value) => value.replace(/[\r\n]+/g, ' ').trim();

const getEnv = (name) => getString(process.env[name]) || getString(import.meta.env[name]);

const escapeHtml = (value) =>
  value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');

const parseRequestBody = async (request) => {
  const contentType = request.headers.get('content-type') || '';

  if (contentType.includes('application/json')) {
    return request.json();
  }

  const formData = await request.formData();
  return Object.fromEntries(formData.entries());
};

export async function POST({ request }) {
  const body = await parseRequestBody(request);
  const botField = getString(body['bot-field']);

  if (botField) {
    return json({ message: 'Missatge enviat correctament.' });
  }

  const name = getString(body.name);
  const email = getString(body.email);
  const recipient = getString(body.recipient) || 'info@afaitaca.org';
  const subject = getString(body.subject) || 'Contacte web';
  const message = getString(body.message);
  const privacyAccepted = body.privacy === true || body.privacy === 'on' || body.privacy === 'true';

  if (!name || name.length < 2) {
    return json({ message: 'El nom és obligatori.' }, 400);
  }

  if (!EMAIL_REGEX.test(email)) {
    return json({ message: 'El correu electrònic no és vàlid.' }, 400);
  }

  if (!RECIPIENTS.has(recipient)) {
    return json({ message: 'El destinatari no és vàlid.' }, 400);
  }

  if (!message || message.length < 10) {
    return json({ message: 'El missatge ha de tenir com a mínim 10 caràcters.' }, 400);
  }

  if (!privacyAccepted) {
    return json({ message: 'Cal acceptar la política de privacitat.' }, 400);
  }

  const smtpUser = getEnv('SMTP_USER');
  const smtpPass = getEnv('SMTP_PASS');
  const smtpHost = getEnv('SMTP_HOST') || 'smtp.gmail.com';
  const smtpPort = getEnv('SMTP_PORT') || '465';
  const contactEmail = getEnv('CONTACT_EMAIL');

  if (!smtpUser || !smtpPass) {
    console.error('SMTP credentials missing in environment variables');
    return json({ message: 'Error de configuració del servidor de correu.' }, 500);
  }

  const transporter = nodemailer.createTransport({
    host: smtpHost,
    port: Number.parseInt(smtpPort, 10),
    secure: smtpPort === '465',
    auth: {
      user: smtpUser,
      pass: smtpPass,
    },
  });

  const mailTo = contactEmail || recipient;
  const safeName = escapeHtml(name);
  const safeEmail = escapeHtml(email);
  const safeRecipient = escapeHtml(recipient);
  const safeSubject = escapeHtml(subject);
  const safeMessage = escapeHtml(message);
  const headerName = stripHeaderLineBreaks(name);
  const headerSubject = stripHeaderLineBreaks(subject);

  try {
    await transporter.sendMail({
      from: `"${headerName}" <${smtpUser}>`,
      to: mailTo,
      replyTo: email,
      subject: `[AFA Ítaca] ${headerSubject} - ${headerName}`,
      text: `
Nom: ${name}
Correu: ${email}
Destinatari seleccionat: ${recipient}
Assumpte: ${subject}

Missatge:
${message}
      `.trim(),
      html: `
        <div style="font-family: Arial, sans-serif; padding: 20px; color: #333; line-height: 1.5;">
          <h2 style="color: #018fd2;">Nou missatge des del formulari de l'AFA Ítaca</h2>
          <p><strong>Nom:</strong> ${safeName}</p>
          <p><strong>Correu:</strong> ${safeEmail}</p>
          <p><strong>Destinatari seleccionat:</strong> ${safeRecipient}</p>
          <p><strong>Assumpte:</strong> ${safeSubject}</p>
          <hr style="border: 0; border-top: 1px solid #eee; margin: 20px 0;" />
          <p><strong>Missatge:</strong></p>
          <p style="white-space: pre-wrap;">${safeMessage}</p>
        </div>
      `,
    });

    return json({ message: 'Missatge enviat correctament.' });
  } catch (error) {
    console.error('Nodemailer error:', error);
    return json({ message: 'No s’ha pogut enviar el missatge. Torna-ho a provar més tard.' }, 500);
  }
}
