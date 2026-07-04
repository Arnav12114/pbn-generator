import {
  Body,
  Button,
  Container,
  Head,
  Heading,
  Hr,
  Html,
  Img,
  Link,
  Preview,
  Section,
  Text,
} from "@react-email/components";

type Props = {
  name?: string;
  previewUrl?: string;
  templateUrl?: string;
  legendUrl?: string;
  siteUrl: string;
};

export function DesignDeliveryEmail({ name, previewUrl, templateUrl, legendUrl, siteUrl }: Props) {
  return (
    <Html>
      <Head />
      <Preview>Your custom paint-by-numbers template and color guide are inside.</Preview>
      <Body style={{ backgroundColor: "#faf7f2", fontFamily: "Georgia, serif", margin: 0 }}>
        <Container style={{ maxWidth: "560px", margin: "0 auto", padding: "40px 24px" }}>
          <Heading style={{ fontSize: "26px", color: "#201a17", fontWeight: 600 }}>
            {name ? `${name}, your` : "Your"} design is ready to paint.
          </Heading>
          <Text style={{ color: "#5a504a", fontSize: "15px", lineHeight: "24px" }}>
            We turned your photo into a numbered painting. Print the template on paper or canvas,
            match your paints to the color guide, and fill in the numbers — dark shades first.
          </Text>
          {previewUrl && (
            <Section style={{ margin: "24px 0" }}>
              <Img
                src={previewUrl}
                alt="Preview of your paint-by-numbers design"
                width="512"
                style={{ width: "100%", borderRadius: "16px" }}
              />
            </Section>
          )}
          {templateUrl && (
            <Button
              href={templateUrl}
              style={{
                backgroundColor: "#c4643c",
                color: "#ffffff",
                padding: "14px 28px",
                borderRadius: "999px",
                fontSize: "15px",
                fontFamily: "Helvetica, Arial, sans-serif",
              }}
            >
              Download your template (PDF)
            </Button>
          )}
          {legendUrl && (
            <Text style={{ fontSize: "14px", marginTop: "16px" }}>
              <Link href={legendUrl} style={{ color: "#c4643c" }}>
                Download the color guide →
              </Link>
            </Text>
          )}
          <Hr style={{ borderColor: "#e8ddcf", margin: "32px 0" }} />
          <Text style={{ color: "#8a7f76", fontSize: "13px", lineHeight: "20px" }}>
            Painting tip: use acrylic craft paint and work from the darkest numbers to the lightest.
            Made another photo you love? <Link href={siteUrl} style={{ color: "#c4643c" }}>Generate another design</Link>.
          </Text>
        </Container>
      </Body>
    </Html>
  );
}

export default DesignDeliveryEmail;
