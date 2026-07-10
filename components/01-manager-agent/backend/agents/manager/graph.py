from langgraph.checkpoint.memory import MemorySaver

from langgraph.graph import END, StateGraph



from agents.manager.nodes import (

    analyze_conversational,

    answer_advisory,

    answer_session_meta_node,

    apply_task_reuse,

    ask_line_ambiguous,

    ask_missing,

    ask_multi_missing,

    ask_time_ambiguous,

    build_plan_message,

    confirm_redirect,

    detect_confirm,

    extract_slots,

    inject_reference_time,

    line_not_found,

    merge_proposals_to_plan,

    merge_slots,

    propose_or_refine_plans,

    reorganize_aim,

    resolve_all_lines,

    resolve_time_filters,

    save_task_definition_node,

    send_to_planner,

    show_suggested_aims,

    sync_session_context,

)

from agents.manager.nodes.saved_plans import (
    activate_saved_plan,
    combine_saved_plans,
    list_saved_plans,
    save_to_shortlist,
)

from agents.manager.nodes.scope import ask_scope_selection

from agents.manager.routing import (

    route_after_confirm,

    route_after_conversational,

    route_after_inject,

    route_after_merge,

    route_after_resolve_all_lines,

    route_after_sync_session_context,

    route_after_time,

)

from agents.manager.state import ManagerState



INTERRUPT_AFTER = [

    "analyze_conversational",

    "ask_missing",

    "ask_multi_missing",

    "ask_time_ambiguous",

    "build_plan_message",

    "confirm_redirect",

    "line_not_found",

    "ask_line_ambiguous",

    "show_suggested_aims",

    "propose_or_refine_plans",

    "answer_session_meta",

    "answer_advisory",

    "ask_scope_selection",

    "save_to_shortlist",

    "list_saved_plans",

]



_checkpointer = MemorySaver()





def build_manager_graph():

    graph = StateGraph(ManagerState)



    graph.add_node("inject_reference_time", inject_reference_time)

    graph.add_node("analyze_conversational", analyze_conversational)

    graph.add_node("extract_slots", extract_slots)

    graph.add_node("merge_slots", merge_slots)

    graph.add_node("resolve_all_lines", resolve_all_lines)

    graph.add_node("sync_session_context", sync_session_context)

    graph.add_node("apply_task_reuse", apply_task_reuse)

    graph.add_node("answer_session_meta", answer_session_meta_node)

    graph.add_node("answer_advisory", answer_advisory)

    graph.add_node("line_not_found", line_not_found)

    graph.add_node("ask_line_ambiguous", ask_line_ambiguous)

    graph.add_node("resolve_time_filters", resolve_time_filters)

    graph.add_node("ask_time_ambiguous", ask_time_ambiguous)

    graph.add_node("ask_missing", ask_missing)

    graph.add_node("ask_multi_missing", ask_multi_missing)

    graph.add_node("show_suggested_aims", show_suggested_aims)

    graph.add_node("propose_or_refine_plans", propose_or_refine_plans)

    graph.add_node("merge_proposals_to_plan", merge_proposals_to_plan)

    graph.add_node("reorganize_aim", reorganize_aim)

    graph.add_node("build_plan_message", build_plan_message)

    graph.add_node("confirm_redirect", confirm_redirect)

    graph.add_node("detect_confirm", detect_confirm)

    graph.add_node("save_task_definition", save_task_definition_node)

    graph.add_node("send_to_planner", send_to_planner)

    graph.add_node("ask_scope_selection", ask_scope_selection)

    graph.add_node("save_to_shortlist", save_to_shortlist)

    graph.add_node("list_saved_plans", list_saved_plans)

    graph.add_node("combine_saved_plans", combine_saved_plans)

    graph.add_node("activate_saved_plan", activate_saved_plan)



    graph.set_entry_point("inject_reference_time")



    graph.add_conditional_edges(

        "inject_reference_time",

        route_after_inject,

        {"detect_confirm": "detect_confirm", "confirm_redirect": "confirm_redirect", "analyze_conversational": "analyze_conversational"},

    )

    graph.add_conditional_edges(

        "analyze_conversational",

        route_after_conversational,

        {"extract_slots": "extract_slots", "__end__": END},

    )

    graph.add_edge("extract_slots", "merge_slots")

    graph.add_conditional_edges(

        "merge_slots",

        route_after_merge,

        {"resolve_all_lines": "resolve_all_lines"},

    )

    graph.add_conditional_edges(

        "resolve_all_lines",

        route_after_resolve_all_lines,

        {

            "ask_multi_missing": "ask_multi_missing",

            "line_not_found": "line_not_found",

            "ask_line_ambiguous": "ask_line_ambiguous",

            "sync_session_context": "sync_session_context",

            "show_suggested_aims": "show_suggested_aims",

            "propose_or_refine_plans": "propose_or_refine_plans",

            "merge_proposals_to_plan": "merge_proposals_to_plan",

            "ask_scope_selection": "ask_scope_selection",

            "save_to_shortlist": "save_to_shortlist",

            "list_saved_plans": "list_saved_plans",

            "combine_saved_plans": "combine_saved_plans",

            "activate_saved_plan": "activate_saved_plan",

            "resolve_time_filters": "resolve_time_filters",

            "ask_missing": "ask_missing",

        },

    )

    graph.add_conditional_edges(

        "sync_session_context",

        route_after_sync_session_context,

        {

            "answer_session_meta": "answer_session_meta",

            "answer_advisory": "answer_advisory",

            "apply_task_reuse": "apply_task_reuse",

            "ask_multi_missing": "ask_multi_missing",

            "line_not_found": "line_not_found",

            "ask_line_ambiguous": "ask_line_ambiguous",

            "show_suggested_aims": "show_suggested_aims",

            "propose_or_refine_plans": "propose_or_refine_plans",

            "merge_proposals_to_plan": "merge_proposals_to_plan",

            "resolve_time_filters": "resolve_time_filters",

            "ask_missing": "ask_missing",

            "reorganize_aim": "reorganize_aim",

            "ask_scope_selection": "ask_scope_selection",

            "save_to_shortlist": "save_to_shortlist",

            "list_saved_plans": "list_saved_plans",

            "combine_saved_plans": "combine_saved_plans",

            "activate_saved_plan": "activate_saved_plan",

            "__end__": END,

        },

    )

    graph.add_edge("apply_task_reuse", "sync_session_context")

    graph.add_edge("line_not_found", END)

    graph.add_edge("ask_line_ambiguous", END)

    graph.add_edge("ask_time_ambiguous", END)

    graph.add_edge("ask_multi_missing", END)

    graph.add_edge("show_suggested_aims", END)

    graph.add_edge("propose_or_refine_plans", END)

    graph.add_edge("answer_session_meta", END)

    graph.add_edge("answer_advisory", END)

    graph.add_edge("ask_scope_selection", END)

    graph.add_edge("save_to_shortlist", END)

    graph.add_edge("list_saved_plans", END)

    graph.add_edge("combine_saved_plans", "build_plan_message")

    graph.add_edge("activate_saved_plan", "build_plan_message")

    graph.add_edge("merge_proposals_to_plan", "build_plan_message")

    graph.add_conditional_edges(

        "resolve_time_filters",

        route_after_time,

        {

            "ask_time_ambiguous": "ask_time_ambiguous",

            "ask_missing": "ask_missing",

            "sync_session_context": "sync_session_context",

        },

    )

    graph.add_edge("reorganize_aim", "build_plan_message")

    graph.add_edge("build_plan_message", END)

    graph.add_edge("confirm_redirect", END)

    graph.add_edge("ask_missing", END)

    graph.add_conditional_edges(

        "detect_confirm",

        route_after_confirm,

        {"save_task_definition": "save_task_definition", "extract_slots": "extract_slots"},

    )

    graph.add_edge("save_task_definition", "send_to_planner")

    graph.add_edge("send_to_planner", END)



    return graph.compile(checkpointer=_checkpointer, interrupt_after=INTERRUPT_AFTER)





manager_graph = build_manager_graph()

