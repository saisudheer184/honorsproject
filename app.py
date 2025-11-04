import streamlit as st
import google.generativeai as genai
import rdflib
import pandas as pd
from pyvis.network import Network
import streamlit.components.v1 as components

# Configure the Gemini API
api_key = "AIzaSyANNuQfJHzCQDhvYK6XxlNsA0DyCk8GtWc"
genai.configure(api_key=api_key)

# Load the RDF graph
@st.cache_resource
def load_graph():
    g = rdflib.Graph()
    g.parse("match.ttl", format="turtle")
    return g

graph = load_graph()

# Function to get SPARQL query from Gemini
def get_sparql_query(question):
    prompt = f"""
    Based on the provided RDF data schema, convert the following natural language question into a SPARQL query.
    The RDF data is about IPL cricket matches and contains information about teams, players, venues, and matches.

    Here are the prefixes used in the data:
    @prefix ex: <http://example.org/ipl/data/> .
    @prefix vocab: <http://example.org/ipl/vocab/> .
    @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
    @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
    @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .

    And here are the key classes and properties:
    Classes: vocab:Match, vocab:Team, vocab:Player, vocab:Venue, vocab:BattingPerformance, vocab:BowlingPerformance
    
    Match Properties: vocab:matchID, vocab:date, vocab:venue, vocab:teamA, vocab:teamB, vocab:winner, vocab:totalRuns_TeamA, vocab:totalRuns_TeamB
    Team Properties: vocab:teamName, vocab:shortName
    Player Properties: vocab:playerName, vocab:playsForTeam, vocab:playerRole, vocab:isStartingXI, vocab:isImpactPlayerIn
    Batting Properties: vocab:runs, vocab:ballsFaced, vocab:notOut, vocab:didNotBat, vocab:atMatch
    Bowling Properties: vocab:overs, vocab:runsConceded, vocab:wicketsTaken, vocab:atMatch
    Venue Properties: vocab:name, vocab:location

    IMPORTANT: The batting and bowling performances are stored as blank nodes connected to players. 
    To access batting data, you need to follow the path: ?player vocab:battingScore ?battingPerf . ?battingPerf vocab:runs ?runs .
    To access bowling data, you need to follow the path: ?player vocab:bowlingScore ?bowlingPerf . ?bowlingPerf vocab:wicketsTaken ?wickets .

    Example queries:
    
    1. Get runs scored by a specific player:
    SELECT ?runs ?ballsFaced WHERE {{
      ?player vocab:playerName "Virat Kohli" .
      ?player vocab:battingScore ?battingPerf .
      ?battingPerf vocab:runs ?runs .
      ?battingPerf vocab:ballsFaced ?ballsFaced .
    }}
    
    2. Get match winner:
    SELECT ?winnerName WHERE {{
      ?match vocab:winner ?winner .
      ?winner vocab:teamName ?winnerName .
    }}
    
    3. Get total runs in a match:
    SELECT ?teamA ?teamB ?runsA ?runsB WHERE {{
      ?match vocab:teamA ?teamA .
      ?match vocab:teamB ?teamB .
      ?match vocab:totalRuns_TeamA ?runsA .
      ?match vocab:totalRuns_TeamB ?runsB .
    }}

    Question: "{question}"

    SPARQL Query:
    """
    model = genai.GenerativeModel('gemini-2.0-flash')
    response = model.generate_content(prompt)
    return response.text.strip().replace("```sparql", "").replace("```", "")

# Function to execute SPARQL query
def execute_sparql_query(query):
    try:
        results = graph.query(query)
        if results:
            # Convert results to a pandas DataFrame
            data = []
            for row in results:
                data.append([str(item) for item in row])
            df = pd.DataFrame(data, columns=[str(var) for var in results.vars])
            return df
        else:
            return "No results found."
    except Exception as e:
        return f"Error executing query: {e}"

def visualize_graph(graph):
    net = Network(height="750px", width="100%", bgcolor="#222222", font_color="white", notebook=True)
    
    # Define prefixes for cleaner labels
    prefixes = {
        "http://example.org/ipl/data/": "ex:",
        "http://example.org/ipl/vocab/": "vocab:",
        "http://www.w3.org/2001/XMLSchema#": "xsd:",
        "http://www.w3.org/2000/01/rdf-schema#": "rdfs:",
        "http://www.w3.org/1999/02/22-rdf-syntax-ns#": "rdf:"
    }
    
    # Helper function to create a readable label
    def create_label(uri):
        uri_str = str(uri)
        for full_prefix, short_prefix in prefixes.items():
            if uri_str.startswith(full_prefix):
                return short_prefix + uri_str[len(full_prefix):]
        return uri_str
    
    # Add nodes and edges with readable labels
    for s, p, o in graph:
        s_label = create_label(s)
        o_label = create_label(o)
        p_label = create_label(p)
        
        net.add_node(str(s), label=s_label, title=s_label)
        net.add_node(str(o), label=o_label, title=o_label)
        net.add_edge(str(s), str(o), label=p_label)
    
    net.show_buttons(filter_=['physics'])
    return net.generate_html()

# Streamlit Chatbot Interface
st.title("Cricket SPARQL Chatbot")

# Initialize session state for navigation
if "current_view" not in st.session_state:
    st.session_state.current_view = "chatbot"

# Add a sidebar with navigation tabs
with st.sidebar:
    st.header("Navigation")
    
    # Navigation tabs
    if st.button("💬 Chatbot", use_container_width=True):
        st.session_state.current_view = "chatbot"
        st.rerun()
    
    if st.button("📊 RDF Graph Visualization", use_container_width=True):
        st.session_state.current_view = "graph"
        st.rerun()
    
    st.markdown("---")
    
    # Sample questions section (only show in chatbot view)
    if st.session_state.current_view == "chatbot":
        with st.expander("Sample Questions", expanded=True):
            st.markdown("- How many runs did Virat Kohli score?")
            st.markdown("- Who won the match between CSK and RCB?")
            st.markdown("- What were Ruturaj Gaikwad's batting stats?")
            st.markdown("- List all players who played for CSK in the match.")
            st.markdown("- How many wickets did Mustafizur Rahman take?")
            st.markdown("- What was the total score for each team?")
        
        if st.button("Clear Chat History"):
            st.session_state.messages = []
            st.rerun()

# Display content based on current view
if st.session_state.current_view == "chatbot":
    st.write("Ask me questions about cricket matches, and I'll provide answers from the knowledge graph.")
    
    # Initialize chat history
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    # Add auto-scrolling functionality
    st.markdown("""
        <script>
            // Auto-scroll to bottom when new messages are added
            function scrollToBottom() {
                const chatContainer = document.querySelector('.main .block-container');
                if (chatContainer) {
                    chatContainer.scrollTop = chatContainer.scrollHeight;
                }
            }
            
            // Scroll to bottom on page load
            window.addEventListener('load', function() {
                setTimeout(scrollToBottom, 500);
            });
            
            // Create observer to watch for new messages
            const observer = new MutationObserver(function(mutations) {
                mutations.forEach(function(mutation) {
                    if (mutation.addedNodes.length) {
                        setTimeout(scrollToBottom, 100);
                    }
                });
            });
            
            // Start observing when DOM is ready
            document.addEventListener('DOMContentLoaded', function() {
                const chatContainer = document.querySelector('.main .block-container');
                if (chatContainer) {
                    observer.observe(chatContainer, { childList: true, subtree: true });
                }
            });
        </script>
    """, unsafe_allow_html=True)

    # Display chat messages from history on app rerun
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if "data" in message and isinstance(message["data"], pd.DataFrame):
                st.dataframe(message["data"])

    # React to user input
    if prompt := st.chat_input("Ask your question here..."):
        # Display user message in chat message container
        st.chat_message("user").markdown(prompt)
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": prompt})

        # Display assistant response in chat message container
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            full_response = ""
            
            # Generate SPARQL query
            with st.spinner("Generating SPARQL query..."):
                try:
                    sparql_query = get_sparql_query(prompt)
                    message_placeholder.code(sparql_query, language="sparql")
                except Exception as e:
                    message_placeholder.error(f"Error generating SPARQL query: {e}")
                    st.stop()
            
            # Execute query and show results
            with st.spinner("Executing query..."):
                try:
                    results = execute_sparql_query(sparql_query)
                    if isinstance(results, pd.DataFrame):
                        st.dataframe(results)
                        st.session_state.messages.append({"role": "assistant", "content": f"Here are the results:\n\n```sparql\n{sparql_query}\n```", "data": results})
                    else:
                        st.markdown(results)
                        st.session_state.messages.append({"role": "assistant", "content": f"Query executed:\n\n```sparql\n{sparql_query}\n```\n\nResults: {results}"})
                except Exception as e:
                    st.error(f"Error executing query: {e}")
                    st.session_state.messages.append({"role": "assistant", "content": f"Error executing query: {e}"})

elif st.session_state.current_view == "graph":
    st.header("RDF Graph Visualization")
    st.write("This is an interactive visualization of the cricket RDF data.")
    
    try:
        html_file = visualize_graph(graph)
        components.html(html_file, height=800)
    except Exception as e:
        st.error(f"Error generating graph visualization: {e}")